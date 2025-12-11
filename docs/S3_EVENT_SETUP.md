# S3 Event Notifications Setup - INSTANT Updates

## Quick Setup (Recommended)

Run the automated setup script:

```bash
cd scripts
chmod +x setup-sns-webhook.sh
./setup-sns-webhook.sh
```

This configures:
- ✅ SNS Topic for S3 events
- ✅ S3 bucket notifications for .xlsx and .csv uploads
- ✅ Webhook subscription to your dashboard
- ✅ Auto-confirmation of subscription

## How It Works

1. **Upload to S3**: You upload a file to `s3://resulam-royalties/`
2. **S3 Event**: S3 detects the upload and sends event to SNS
3. **SNS Notification**: SNS sends HTTPS POST to `/api/s3-webhook`
4. **Instant Download**: Webhook triggers immediate S3 download
5. **Dashboard Update**: Data reflects on next page refresh

**Result**: 0-5 second delay vs 5-minute polling!

## Manual Setup Steps

### 1. Create SNS Topic

```bash
aws sns create-topic --name resulam-s3-uploads --region us-east-1
```

### 2. Get Topic ARN

```bash
TOPIC_ARN=$(aws sns list-topics --query "Topics[?contains(TopicArn, 'resulam-s3-uploads')].TopicArn" --output text)
echo $TOPIC_ARN
```

### 3. Set SNS Permissions

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws sns set-topic-attributes \
  --topic-arn $TOPIC_ARN \
  --attribute-name Policy \
  --attribute-value '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "s3.amazonaws.com"},
      "Action": "SNS:Publish",
      "Resource": "'$TOPIC_ARN'",
      "Condition": {
        "StringEquals": {"aws:SourceAccount": "'$ACCOUNT_ID'"},
        "ArnLike": {"aws:SourceArn": "arn:aws:s3:::resulam-royalties"}
      }
    }]
  }'
```

### 4. Subscribe Webhook

```bash
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol https \
  --notification-endpoint https://resulam-royalties.tchamna.com/api/s3-webhook \
  --region us-east-1
```

**Note**: SNS will send a confirmation request to your webhook. The app auto-confirms it.

### 5. Configure S3 Notifications

```bash
aws s3api put-bucket-notification-configuration \
  --bucket resulam-royalties \
  --notification-configuration '{
    "TopicConfigurations": [{
      "TopicArn": "'$TOPIC_ARN'",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [{
            "Name": "suffix",
            "Value": ".xlsx"
          }]
        }
      }
    }]
  }'
```

## Testing

### Test the Webhook Endpoint

```bash
# Check if webhook is active
curl https://resulam-royalties.tchamna.com/api/webhook-status

# Expected response:
# {
#   "status": "active",
#   "endpoints": {...}
# }
```

### Test with File Upload

```bash
# Upload a test file
aws s3 cp /path/to/test.xlsx s3://resulam-royalties/

# Check container logs for instant sync
docker logs resulam-royalties --tail 50
```

You should see:
```
⚡ INSTANT SYNC: Downloading test.xlsx from S3...
✅ Successfully synced test.xlsx
```

## Verify Setup

```bash
# Check SNS subscription status
aws sns list-subscriptions-by-topic \
  --topic-arn $TOPIC_ARN \
  --region us-east-1

# Check S3 notification config
aws s3api get-bucket-notification-configuration \
  --bucket resulam-royalties
```

## Troubleshooting

### Webhook not receiving notifications?

1. **Check subscription status**:
   ```bash
   aws sns list-subscriptions --region us-east-1 | grep resulam
   ```
   Status should be "Confirmed", not "PendingConfirmation"

2. **Check container logs**:
   ```bash
   docker logs resulam-royalties | grep -i webhook
   ```

3. **Verify HTTPS access**:
   ```bash
   curl https://resulam-royalties.tchamna.com/api/s3-webhook
   ```
   Should return: `{"status": "ok"}`

### Still using polling?

Background sync (10-minute intervals) runs as a fallback. Even if SNS fails, you'll get updates every 10 minutes.

## Cleanup

To remove SNS setup:

```bash
# Delete SNS topic
aws sns delete-topic --topic-arn $TOPIC_ARN --region us-east-1

# Remove S3 notifications
aws s3api put-bucket-notification-configuration \
  --bucket resulam-royalties \
  --notification-configuration '{}' \
  --region us-east-1
```

## Current Architecture

```
┌─────────────┐
│  Upload to  │
│  S3 Bucket  │
└──────┬──────┘
       │
       ↓ (instant)
┌─────────────┐
│ S3 Event    │
│ Notification│
└──────┬──────┘
       │
       ↓
┌─────────────┐
│  SNS Topic  │
└──────┬──────┘
       │
       ↓ (HTTPS POST)
┌─────────────────────┐
│ Dashboard Webhook   │
│ /api/s3-webhook     │
└──────┬──────────────┘
       │
       ↓ (downloads file)
┌─────────────────────┐
│ Container Data Dir  │
└─────────────────────┘
       │
       ↓ (on page refresh)
┌─────────────────────┐
│ Dashboard Shows     │
│ Updated Data        │
└─────────────────────┘
```

**Fallback**: Background polling every 10 minutes ensures reliability even if webhook fails.

## Cost

- SNS: ~$0.50 per 1 million notifications
- S3 Events: Free
- Webhook calls: Free

For typical usage (few uploads per day): **< $0.01/month**
