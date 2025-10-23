# Render Deployment Guide for USF Moving AI Agent

## ✅ Deployment Readiness Checklist

Your application is now ready for Render deployment with the following files:

- ✅ `app.py` - Main Flask application
- ✅ `requirements.txt` - Python dependencies (includes gunicorn)
- ✅ `Procfile` - Process file for Render
- ✅ `render.yaml` - Render configuration (optional but recommended)
- ✅ `runtime.txt` - Python version specification
- ✅ `.env` - Environment variables (local only, NOT pushed to git)

## 🚀 Deployment Steps

### 1. Push to GitHub

Make sure your code is pushed to your repository:

```bash
git add .
git commit -m "Add Render deployment configuration"
git push origin main
```

### 2. Create Render Account

1. Go to https://render.com
2. Sign up or log in (can use GitHub authentication)

### 3. Create New Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository: `usfmoving-eng/Callagent`
3. Configure the service:
   - **Name**: `usf-moving-ai-agent` (or your preferred name)
   - **Region**: Choose closest to your users
   - **Branch**: `main`
   - **Root Directory**: Leave blank
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: Free (or Starter for production)

### 4. Configure Environment Variables

In the Render dashboard, add all these environment variables (from your `.env` file):

#### Required Variables:
- `TWILIO_ACCOUNT_SID` - Your Twilio Account SID
- `TWILIO_AUTH_TOKEN` - Your Twilio Auth Token
- `TWILIO_PHONE_NUMBER` - Your Twilio phone number
- `GOOGLE_MAPS_API_KEY` - Google Maps API key
- `BOOKING_SHEET_ID` - Google Sheets ID for bookings
- `GOOGLE_SHEETS_CREDS` - **Full JSON content** of service account (one line)
- `OPENAI_API_KEY` - OpenAI API key
- `EMAIL_ADDRESS` - Gmail address for notifications
- `EMAIL_PASSWORD` - Gmail app password
- `MANAGER_EMAIL` - Manager's email for notifications

#### Optional Variables (with defaults):
- `FLASK_ENV` = `production`
- `SMTP_SERVER` = `smtp.gmail.com`
- `SMTP_PORT` = `587`
- `PORT` = Auto-assigned by Render
- `ENABLE_CALL_RECORDING` = `True`
- `ENABLE_EMAIL_NOTIFICATIONS` = `True`
- `ENABLE_SMS_NOTIFICATIONS` = `True`

**Important**: For `GOOGLE_SHEETS_CREDS`, copy the entire JSON content from your service account file as a single line (no line breaks).

### 5. Deploy

1. Click **"Create Web Service"**
2. Render will automatically:
   - Clone your repository
   - Install dependencies
   - Start the application
3. Wait for deployment to complete (usually 2-5 minutes)

### 6. Get Your Deployment URL

After successful deployment, you'll get a URL like:
```
https://usf-moving-ai-agent.onrender.com
```

### 7. Update Twilio Webhooks

Configure your Twilio phone number webhooks with your new Render URL:

1. Go to Twilio Console → Phone Numbers → Active Numbers
2. Select your number
3. Update webhooks:
   - **Voice & Fax** → **A CALL COMES IN**: 
     - `https://your-app.onrender.com/voice/inbound` (HTTP POST)
   - **Messaging** → **A MESSAGE COMES IN**: 
     - `https://your-app.onrender.com/sms/incoming` (HTTP POST)
   - **Voice Status Callback** (optional):
     - `https://your-app.onrender.com/voice/status` (HTTP POST)
4. Save changes

### 8. Test Your Deployment

Test these endpoints:

```bash
# Health check
curl https://your-app.onrender.com/health

# Outbound call test (optional)
curl -X POST https://your-app.onrender.com/outbound/lead \
  -H "Content-Type: application/json" \
  -d '{"phone":"+1234567890","name":"Test User","email":"test@example.com"}'
```

## 🔧 Post-Deployment Configuration

### Auto-Deploy on Git Push

Render automatically deploys when you push to the `main` branch. To disable:
- Go to Settings → Build & Deploy → Auto-Deploy: OFF

### Custom Domain (Optional)

1. Go to Settings → Custom Domain
2. Add your domain (e.g., `calls.usfhoustonmoving.com`)
3. Update DNS records as instructed

### Monitoring

- **Logs**: Available in Render dashboard under "Logs" tab
- **Metrics**: View CPU, memory, and bandwidth usage
- **Health Check**: Render monitors `/health` endpoint

## ⚠️ Important Notes

### Free Tier Limitations:
- Services spin down after 15 minutes of inactivity
- First request after spin-down takes 30-60 seconds (cold start)
- 750 hours/month free

### For Production:
- Upgrade to **Starter** plan ($7/month) for:
  - No spin-down
  - Faster cold starts
  - Custom domains with SSL

### Environment Variables:
- Never commit `.env` file to git
- Always use Render's environment variable management
- Use "secret files" for large credentials if needed

### Database Considerations:
- Currently using in-memory `call_sessions` dictionary
- For production with multiple instances, consider:
  - Redis (Render Redis or external)
  - PostgreSQL for persistent storage

## 🐛 Troubleshooting

### Build Fails:
- Check Python version in `runtime.txt` matches your local
- Verify all dependencies in `requirements.txt`
- Check build logs in Render dashboard

### App Crashes on Start:
- Check environment variables are set correctly
- Review logs for missing credentials
- Verify `GOOGLE_SHEETS_CREDS` is valid JSON

### Twilio Webhooks Not Working:
- Verify webhook URLs in Twilio console
- Check that URLs use HTTPS (not HTTP)
- Review Render logs for incoming requests

### Cold Starts (Free Tier):
- First call after inactivity will be slow
- Consider upgrading to paid tier for production
- Or keep service warm with external pinger (not recommended for free tier)

## 📊 Monitoring & Logs

View real-time logs:
```bash
# In Render dashboard, go to Logs tab
# Or use Render CLI:
render logs -t usf-moving-ai-agent
```

## 🔄 Updating Your App

```bash
# Make changes locally
git add .
git commit -m "Your update message"
git push origin main

# Render will automatically deploy the changes
```

## 📞 Support

- Render Documentation: https://render.com/docs
- Twilio Support: https://www.twilio.com/support
- GitHub Issues: https://github.com/usfmoving-eng/Callagent/issues

---

**Your app is ready to deploy! Follow the steps above and you'll be live in minutes.** 🚀
