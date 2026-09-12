# 🚀 Travel Planner - 5-Minute Deployment

## Option 1: Local Docker (Easiest - 2 minutes)

```bash
# Ensure Docker & Docker Compose installed
docker-compose up --build

# Visit http://localhost:8000
```

✅ **Done!** Server runs locally with auto-reload.

---

## Option 2: Heroku (Free-ish - 3 minutes)

### Prerequisites
- Heroku account (free tier available)
- Git installed
- `heroku` CLI installed

### Deploy

```bash
# Login to Heroku
heroku login

# Create app
heroku create travel-planner

# Set API keys
heroku config:set GEMINI_API_KEY=your_key
heroku config:set TAVILY_API_KEY=your_key

# Deploy
git push heroku main

# View logs
heroku logs --tail

# Visit https://travel-planner.herokuapp.com
```

✅ **Live on Heroku!** Auto-scales, SSL included.

**Cost:** Free tier (550 dyno hours/month) or $7/month paid.

---

## Option 3: AWS App Runner (Best - 5 minutes)

### Prerequisites
- AWS account
- AWS CLI installed & configured
- Docker installed

### Deploy

```bash
# Set environment variables
export AWS_ACCOUNT_ID=123456789
export AWS_REGION=us-east-1

# Run deployment script
chmod +x deploy.sh
./deploy.sh aws-apprunner

# Check status
aws apprunner list-services --region $AWS_REGION
```

✅ **Running on AWS!** Production-grade auto-scaling.

**Cost:** ~$30-50/month

---

## Option 4: Railway.app (Modern - 2 minutes)

### Prerequisites
- Railway.app account (free tier)
- GitHub repo connected

### Deploy

1. Go to [railway.app](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub"
4. Choose this repo
5. Add environment variables:
   - `GEMINI_API_KEY`
   - `TAVILY_API_KEY`
6. Deploy

✅ **Live on Railway!** Modern, simple, fast.

**Cost:** $5 credit/month free, then pay-as-you-go ($0.10/hour per service).

---

## Comparison Table

| Option | Speed | Cost | Scalability | Maintenance |
|--------|-------|------|-------------|-------------|
| Local Docker | 2 min | $0 | Single machine | Manual |
| Heroku | 3 min | Free-$7 | Auto-scales | Zero |
| AWS App Runner | 5 min | $30-50 | Auto-scales | Low |
| Railway.app | 2 min | Free-$50 | Auto-scales | Zero |
| ECS on Fargate | 20 min | $50-100 | Full control | Medium |

---

## What Gets Deployed

✅ FastAPI backend (all 5 agents)
✅ Frontend (HTML/CSS/JS)
✅ SQLite database
✅ PDF export
✅ Multi-language support
✅ Automatic itinerary saving
✅ API testing collection

---

## Post-Deployment Checklist

After deploying to production:

- [ ] Test health endpoint: `curl https://your-url/health`
- [ ] Generate sample itinerary: `curl -X POST https://your-url/api/plan -d '{...}'`
- [ ] Check logs for errors
- [ ] Verify API keys are set (never in code!)
- [ ] Set up monitoring/alerts
- [ ] Configure auto-scaling
- [ ] Set up database backups
- [ ] Enable SSL/HTTPS
- [ ] Add custom domain
- [ ] Share URL with users

---

## Custom Domain

### For Heroku
```bash
heroku domains:add api.example.com
# Then update DNS CNAME to: api.example.com.herokudns.com
```

### For AWS App Runner
```bash
# Use Route 53 or your DNS provider
# Point to the App Runner URL
```

### For Railway.app
- Dashboard → Settings → Domains
- Add custom domain
- Update DNS records

---

## Monitoring

### Heroku
```bash
heroku logs --tail
heroku metrics
heroku addons:create papertrail:choklad  # Add logging
```

### AWS App Runner
```bash
aws apprunner describe-service --service-arn <arn>
# Check CloudWatch logs
```

### Railway.app
- Dashboard shows real-time logs
- Built-in error tracking

---

## Scaling

### Heroku
```bash
# Upgrade dyno
heroku dyno:scale web=2:professional

# View resources
heroku ps
```

### AWS App Runner
Auto-scales by default (up to 10 instances)

### Railway.app
Configure CPU/Memory in dashboard

---

## Environment Variables

**Required in production:**

```bash
GEMINI_API_KEY=sk-xxx...
TAVILY_API_KEY=tvly-xxx...
```

**Optional:**

```bash
MAX_RETRIES=3
MAX_POIS_PER_DAY=5
MAX_HOURS_PER_DAY=10
MAX_POIS_TOTAL=30
```

---

## Troubleshooting

### App won't start
```bash
# Check logs
heroku logs --tail
docker logs travel-planner

# Verify env vars
heroku config
```

### API returns 500
```bash
# Check API keys
echo $GEMINI_API_KEY
echo $TAVILY_API_KEY

# Verify they're set on deployment platform
```

### Slow responses
```bash
# Check if Gemini API is slow
# Check network latency
# Consider caching results

# Increase timeout if needed
# Update uvicorn: --timeout-keep-alive 120
```

### Out of memory
```bash
# Upgrade instance size
heroku dyno:scale web=2:standard-1x
```

---

## Recommended: Railway.app ⭐

**Why?**
1. Easiest deployment (2 minutes)
2. Modern UI
3. Good free tier ($5 credit)
4. No credit card for free tier
5. Auto-deploys on git push
6. Great logs and monitoring

**Deploy now:**
```bash
git push  # Pushes to GitHub
# Railway auto-detects and deploys automatically
```

---

## Production Checklist

```
PRE-LAUNCH
- [ ] All tests passing
- [ ] API keys rotated and secured
- [ ] CORS configured for your domain
- [ ] Rate limiting enabled
- [ ] Error tracking configured (Sentry)
- [ ] Uptime monitoring set up (Pingdom)
- [ ] Database backups configured
- [ ] SSL certificate installed
- [ ] Custom domain working

LAUNCH DAY
- [ ] Team notified
- [ ] Monitoring dashboard open
- [ ] Support ready
- [ ] Incident response plan ready

POST-LAUNCH
- [ ] Monitor error rates
- [ ] Check response times
- [ ] Verify no API key leaks
- [ ] Review user feedback
- [ ] Plan next improvements
```

---

## Questions?

See:
- `DEPLOYMENT.md` - Detailed AWS/Docker/ECS setup
- `API_TESTING_GUIDE.md` - API docs & testing
- `CODE_QUALITY_GUIDE.md` - Architecture & optimization

🚀 **Choose your platform and deploy in under 5 minutes!**
