"""
SNS Webhook Handler for S3 Events
Receives instant notifications when files are uploaded to S3
"""
import json
import logging
from flask import Blueprint, request, jsonify
from src.utils.s3_sync import download_s3_files
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Create Flask blueprint for webhooks
webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api')


@webhooks_bp.route('/s3-webhook', methods=['POST', 'GET'])
def s3_webhook():
    """
    Endpoint to receive SNS notifications for S3 upload events.
    SNS sends both subscription confirmations and notifications.
    """
    
    # Log request for debugging
    logger.info(f"Received webhook request: {request.method}")
    
    # Handle GET request (for testing)
    if request.method == 'GET':
        return jsonify({
            "status": "ok",
            "message": "S3 webhook endpoint is active",
            "endpoint": "/api/s3-webhook"
        }), 200
    
    # Get request data
    try:
        # SNS sends JSON in the request body
        if request.content_type == 'text/plain':
            data = json.loads(request.data.decode('utf-8'))
        else:
            data = request.get_json(force=True)
        
        message_type = request.headers.get('x-amz-sns-message-type', data.get('Type'))
        
        logger.info(f"SNS Message Type: {message_type}")
        
        # Handle SNS subscription confirmation
        if message_type == 'SubscriptionConfirmation':
            subscribe_url = data.get('SubscribeURL')
            logger.info(f"SNS Subscription Confirmation received")
            logger.info(f"Please visit this URL to confirm: {subscribe_url}")
            
            # Auto-confirm subscription (optional - for security, you may want manual confirmation)
            import requests
            try:
                response = requests.get(subscribe_url, timeout=10)
                if response.status_code == 200:
                    logger.info("SNS subscription confirmed successfully!")
                    return jsonify({"status": "confirmed"}), 200
            except Exception as e:
                logger.error(f"Failed to auto-confirm subscription: {e}")
            
            return jsonify({
                "status": "pending",
                "message": "Subscription confirmation required",
                "subscribe_url": subscribe_url
            }), 200
        
        # Handle SNS notification
        elif message_type == 'Notification':
            # Parse the message
            message = json.loads(data.get('Message', '{}'))
            
            # Extract S3 event details
            if 'Records' in message:
                for record in message['Records']:
                    event_name = record.get('eventName', '')
                    
                    # Check if this is a file upload event
                    if event_name.startswith('ObjectCreated'):
                        s3_info = record.get('s3', {})
                        bucket = s3_info.get('bucket', {}).get('name')
                        s3_key = s3_info.get('object', {}).get('key')
                        
                        logger.info(f"🔔 S3 Upload Detected: s3://{bucket}/{s3_key}")
                        
                        # Check if this is one of our data files
                        if s3_key.endswith('.xlsx') or s3_key.endswith('.csv'):
                            # Trigger immediate download
                            try:
                                # Determine data directory
                                if os.path.exists('/app'):
                                    data_dir = Path('/app/data')
                                else:
                                    project_root = Path(__file__).parent.parent.parent
                                    data_dir = project_root / "data"
                                
                                local_path = str(data_dir / s3_key)
                                region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
                                
                                # Download the file
                                print(f"\n⚡ INSTANT SYNC: Downloading {s3_key} from S3...")
                                success = download_s3_files(
                                    bucket=bucket,
                                    files=[(s3_key, local_path)],
                                    region=region,
                                    quiet=False
                                )
                                
                                if success:
                                    logger.info(f"✅ Successfully synced {s3_key}")
                                    print(f"✅ Dashboard will reflect new data on next page refresh")
                                    return jsonify({
                                        "status": "success",
                                        "message": f"File {s3_key} downloaded successfully",
                                        "bucket": bucket,
                                        "key": s3_key
                                    }), 200
                                else:
                                    logger.error(f"Failed to download {s3_key}")
                                    return jsonify({
                                        "status": "error",
                                        "message": f"Failed to download {s3_key}"
                                    }), 500
                                    
                            except Exception as e:
                                logger.error(f"Error processing S3 event: {e}")
                                return jsonify({
                                    "status": "error",
                                    "message": str(e)
                                }), 500
            
            return jsonify({"status": "processed"}), 200
        
        else:
            logger.warning(f"Unknown message type: {message_type}")
            return jsonify({
                "status": "ignored",
                "message": f"Unknown message type: {message_type}"
            }), 200
            
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@webhooks_bp.route('/webhook-status', methods=['GET'])
def webhook_status():
    """Check webhook endpoint status"""
    return jsonify({
        "status": "active",
        "endpoints": {
            "s3_webhook": "/api/s3-webhook",
            "status": "/api/webhook-status"
        },
        "message": "Webhook endpoints are active and ready to receive SNS notifications"
    }), 200
