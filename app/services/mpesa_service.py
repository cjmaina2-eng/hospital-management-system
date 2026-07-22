"""
M-Pesa Payment Service using Daraja API Integration
Handles M-Pesa STK Push, payment callbacks, and transaction verification
"""

import os
import json
import requests
from datetime import datetime
from decimal import Decimal
from base64 import b64encode
from flask import current_app
import logging

logger = logging.getLogger(__name__)


class MpesaService:
    """Service for handling M-Pesa payments via Daraja API"""
    
    # Daraja API endpoints
    AUTH_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    STK_PUSH_URL = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    TRANSACTION_QUERY_URL = "https://sandbox.safaricom.co.ke/mpesa/transactionstatus/v1/query"
    
    def __init__(self):
        """Initialize M-Pesa service with Daraja credentials"""
        self.consumer_key = os.environ.get('MPESA_CONSUMER_KEY', '')
        self.consumer_secret = os.environ.get('MPESA_CONSUMER_SECRET', '')
        self.business_short_code = os.environ.get('MPESA_SHORTCODE', '174379')
        self.passkey = os.environ.get('MPESA_PASSKEY', '')
        self.callback_url = os.environ.get('MPESA_CALLBACK_URL', '')
        self.access_token = None
        self.token_expires_at = None
    
    def generate_access_token(self):
        """
        Generate access token from Daraja API
        Returns: str - Bearer token for API calls
        """
        try:
            # Create basic auth header
            credentials = f"{self.consumer_key}:{self.consumer_secret}"
            encoded_credentials = b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(self.AUTH_URL, headers=headers, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            logger.info("M-Pesa access token generated successfully")
            return self.access_token
            
        except Exception as e:
            logger.error(f"Failed to generate M-Pesa access token: {str(e)}")
            raise
    
    def get_access_token(self):
        """Get valid access token, regenerate if needed"""
        if not self.access_token:
            self.generate_access_token()
        return self.access_token
    
    def generate_password(self, timestamp):
        """
        Generate password for STK push request
        Password = base64(shortcode + passkey + timestamp)
        """
        password_string = f"{self.business_short_code}{self.passkey}{timestamp}"
        password = b64encode(password_string.encode()).decode()
        return password
    
    def initiate_stk_push(self, phone_number, amount, bill_id, party_name="Hospital Bill"):
        """
        Initiate STK push for M-Pesa payment
        
        Args:
            phone_number (str): Customer phone number (format: 2547XXXXXXXX)
            amount (Decimal/float/int): Amount in KES
            bill_id (int): Bill ID for reference
            party_name (str): Description of the payment
            
        Returns:
            dict: Response from Daraja API with checkout request ID
        """
        try:
            # Validate phone number
            if not phone_number.startswith('254'):
                phone_number = '254' + phone_number.lstrip('0')
            
            # Get access token
            access_token = self.get_access_token()
            
            # Generate timestamp and password
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            # Prepare STK push payload
            payload = {
                "BusinessShortCode": self.business_short_code,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(float(amount)),  # Daraja expects integer
                "PartyA": phone_number,
                "PartyB": self.business_short_code,
                "PhoneNumber": phone_number,
                "CallBackURL": self.callback_url,
                "AccountReference": f"Bill-{bill_id}",
                "TransactionDesc": party_name,
                "Remark": f"Payment for {party_name}"
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.STK_PUSH_URL,
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            response_data = response.json()
            logger.info(f"STK Push initiated successfully for bill {bill_id}")
            return response_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"M-Pesa STK push failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error initiating M-Pesa payment: {str(e)}")
            raise
    
    def query_transaction_status(self, checkout_request_id):
        """
        Query the status of a payment transaction
        
        Args:
            checkout_request_id (str): The checkout request ID from STK push
            
        Returns:
            dict: Transaction status response
        """
        try:
            access_token = self.get_access_token()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            payload = {
                "BusinessShortCode": self.business_short_code,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.TRANSACTION_QUERY_URL,
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error querying transaction status: {str(e)}")
            raise
    
    @staticmethod
    def process_callback(callback_data):
        """
        Process M-Pesa callback from Daraja
        
        Args:
            callback_data (dict): Callback data from Daraja
            
        Returns:
            dict: Processed transaction data
        """
        try:
            # Extract result code and message
            result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode', -1)
            result_desc = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultDesc', 'Unknown error')
            
            if result_code == 0:
                # Success
                callback_metadata = callback_data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {})
                items = callback_metadata.get('Item', [])
                
                transaction_data = {
                    'status': 'success',
                    'result_code': result_code,
                    'result_desc': result_desc,
                    'transaction_amount': None,
                    'mpesa_receipt_number': None,
                    'transaction_date': None,
                    'phone_number': None,
                    'checkout_request_id': callback_data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
                }
                
                # Extract metadata
                for item in items:
                    name = item.get('Name')
                    value = item.get('Value')
                    
                    if name == 1:  # Amount
                        transaction_data['transaction_amount'] = Decimal(str(value))
                    elif name == 2:  # MpesaReceiptNumber
                        transaction_data['mpesa_receipt_number'] = str(value)
                    elif name == 3:  # TransactionDate
                        transaction_data['transaction_date'] = str(value)
                    elif name == 4:  # PhoneNumber
                        transaction_data['phone_number'] = str(value)
                
                return transaction_data
            else:
                # Failed transaction
                return {
                    'status': 'failed',
                    'result_code': result_code,
                    'result_desc': result_desc,
                    'checkout_request_id': callback_data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
                }
                
        except Exception as e:
            logger.error(f"Error processing M-Pesa callback: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
