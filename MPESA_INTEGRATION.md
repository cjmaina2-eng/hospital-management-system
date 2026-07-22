# M-Pesa Integration Setup Guide (Daraja API)

## Overview
This hospital management system now supports M-Pesa payments through Daraja integration. The implementation allows receptionist staff to initiate M-Pesa STK push prompts for patient bill payments.

## Changes Made

### 1. **Access Control Restrictions**
- **Billing Operations**: Now restricted to `receptionist` and `admin` roles only
- **Discharge Operations**: Now restricted to `receptionist` and `admin` roles only
  - Previously doctors could process discharge, now only reception desk staff can
- Updated error messages to reflect these role restrictions

### 2. **Database Model Updates**
Added M-Pesa-specific fields to the `Bill` model in [app/models/billing.py](app/models/billing.py):
- `mpesa_checkout_request_id`: Stores the Daraja checkout request ID
- `mpesa_receipt_number`: M-Pesa transaction receipt number
- `mpesa_phone_number`: Customer's M-Pesa phone number
- `mpesa_transaction_date`: Timestamp of the M-Pesa transaction

### 3. **New Service Module**
Created [app/services/mpesa_service.py](app/services/mpesa_service.py) with:
- `MpesaService` class for handling Daraja API interactions
- STK push initiation
- Transaction status queries
- Callback processing
- Access token management

### 4. **New Routes**
Added to [app/routes/billing.py](app/routes/billing.py):

#### `/billing/mpesa/initiate/<bill_id>` (POST)
- Initiates M-Pesa STK push for payment
- Parameters: `phone_number` (required, format: 254XXXXXXXXX)
- Returns JSON response with checkout request ID
- Permission: Patient can pay own bills, receptionist/admin can process any

#### `/billing/mpesa/callback` (POST)
- Receives M-Pesa payment confirmation from Daraja
- Automatically updates bill status when payment is received
- Updates M-Pesa receipt number and transaction date
- Always returns 200 OK to acknowledge receipt

#### `/billing/mpesa/check_status/<bill_id>` (GET)
- Query current payment status of M-Pesa transaction
- Returns JSON with bill status and payment details
- Used for real-time status polling on payment page

### 5. **Updated Templates**
- **[app/templates/billing/pay.html](app/templates/billing/pay.html)**: Enhanced payment UI with M-Pesa option, phone number input, and real-time status checking
- **[app/templates/billing/new.html](app/templates/billing/new.html)**: Added M-Pesa to payment method dropdown
- **[app/templates/billing/edit.html](app/templates/billing/edit.html)**: Added M-Pesa to payment method dropdown
- **[app/templates/billing/view.html](app/templates/billing/view.html)**: Shows M-Pesa receipt details when available

## Daraja API Setup

### Prerequisites
1. **Create Daraja Developer Account**
   - Go to https://developer.safaricom.co.ke
   - Sign up and create an application
   - Get your credentials:
     - Consumer Key
     - Consumer Secret
     - Short Code (for receiving payments)
     - Passkey (used for password generation)

2. **Environment Variables**
   Add the following to your `.env` file:
   ```
   MPESA_CONSUMER_KEY=your_consumer_key
   MPESA_CONSUMER_SECRET=your_consumer_secret
   MPESA_SHORTCODE=your_business_shortcode
   MPESA_PASSKEY=your_passkey
   MPESA_CALLBACK_URL=https://yourdomain.com/billing/mpesa/callback
   ```

### Daraja API Endpoints (Sandbox)
- **Authentication**: `https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials`
- **STK Push**: `https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest`
- **Transaction Query**: `https://sandbox.safaricom.co.ke/mpesa/transactionstatus/v1/query`

### Production Deployment
When moving to production:
1. Update endpoints from `sandbox.safaricom.co.ke` to `api.safaricom.co.ke`
2. Get production credentials from Daraja
3. Update environment variables
4. Update `MPESA_CALLBACK_URL` to your production domain
5. Ensure HTTPS is enabled for callback endpoint

## Usage Workflow

### For Reception Desk Staff:
1. Create or view a bill
2. Click "Pay Now" button
3. Select "M-Pesa" payment method
4. Enter customer's phone number (format: 7XXXXXXXX or 254XXXXXXXXX)
5. Click "Send M-Pesa Prompt"
6. System will display status and poll for payment confirmation
7. When payment is received, bill automatically updates to "Paid"

### For Patients:
1. Navigate to bill payment page
2. Select M-Pesa payment method
3. Enter phone number and send prompt
4. Complete M-Pesa authentication on their phone
5. Payment processes automatically

## Testing (Sandbox Mode)

### Test Credentials
- **Consumer Key/Secret**: Get from Daraja dashboard
- **Test Phone Numbers**: Use 254712345678 (Safaricom test numbers)
- **Test Amounts**: Any amount under 10,000 KES

### Daraja Test Portal
- Access: https://developer.safaricom.co.ke/test
- Use test credentials to simulate payments

## Callback Configuration

### Important Security Notes:
1. **Whitelist Daraja IP addresses** in your firewall
2. **Validate all callbacks** before processing
3. **Always return 200 OK** even on errors to prevent Daraja retries
4. **Log all transactions** for audit purposes
5. **Use HTTPS** in production

### Callback Format
```json
{
  "Body": {
    "stkCallback": {
      "MerchantRequestID": "...",
      "CheckoutRequestID": "...",
      "ResultCode": 0,
      "ResultDesc": "The service request has been accepted...",
      "CallbackMetadata": {
        "Item": [
          {"Name": 1, "Value": 1000},      // Amount
          {"Name": 2, "Value": "ABC123"},  // M-Pesa receipt
          {"Name": 3, "Value": "..."},     // Transaction date
          {"Name": 4, "Value": "254712..."}// Phone number
        ]
      }
    }
  }
}
```

## Database Migration

After deployment, run:
```bash
# Generate migration
flask db migrate -m "Add M-Pesa fields to Bill model"

# Apply migration
flask db upgrade
```

## Troubleshooting

### STK Push Not Appearing
- Verify phone number format (must be 254XXXXXXXXX)
- Check Daraja credentials are correct
- Ensure callback URL is publicly accessible
- Review Daraja API response in logs

### Payment Not Recorded
- Verify callback URL is in config
- Check firewall/WAF isn't blocking Daraja IPs
- Review application logs for errors
- Ensure database migration was applied

### Common Errors
- **E_INVALID_SUBSCRIBER_IDENTITY**: Invalid phone number format
- **INVALID_CREDENTIALS**: Wrong Consumer Key/Secret
- **INVALID_SHORTCODE**: Shortcode not configured in Daraja

## Files Modified

1. `app/models/billing.py` - Added M-Pesa fields to Bill model
2. `app/routes/billing.py` - Added M-Pesa routes and imports
3. `app/routes/patient.py` - Restricted discharge to reception only
4. `app/services/mpesa_service.py` - New M-Pesa service module
5. `app/templates/billing/pay.html` - Enhanced UI with M-Pesa payment
6. `app/templates/billing/new.html` - Added M-Pesa option
7. `app/templates/billing/edit.html` - Added M-Pesa option
8. `app/templates/billing/view.html` - Show M-Pesa transaction details
9. `requirements.txt` - Added `requests` library

## Next Steps

1. Configure Daraja credentials in `.env`
2. Run database migrations
3. Test in sandbox environment
4. Deploy to staging for UAT
5. Move to production with proper credentials
