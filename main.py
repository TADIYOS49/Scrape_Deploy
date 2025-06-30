#!/usr/bin/env python3
"""
Cloud Run HTTP wrapper for Browserbase scraper with Swagger UI
This creates an HTTP endpoint that Cloud Scheduler can trigger
Enhanced with better API organization and error handling
"""

import os
import sys
from flask import Flask, request, jsonify, send_file
from flask_restx import Api, Resource, fields, Namespace
from google.cloud import storage
import tempfile
import shutil
from browserbase_scraper import main as run_scraper
from datetime import datetime
import pandas as pd
import threading
import time

app = Flask(__name__)

# Enhanced API with Swagger UI for Cloud Run
api = Api(
    app,
    version='2.0.0',
    title='Browserbase Property Scraper API (Cloud Run)',
    description='Enhanced property scraper with Google Cloud Storage integration',
    doc='/swagger/',
    prefix='/api'
)

# Configure for Cloud Run
PORT = int(os.environ.get("PORT", 8080))
BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "your-scraper-results")

# Global processing state
processing_state = {
    "is_running": False,
    "current_task": None,
    "start_time": None,
    "progress": None,
    "error": None
}

# Create namespaces
ns_scraper = Namespace('scraper', description='Property scraping operations')
ns_management = Namespace('management', description='File management operations')  
ns_monitoring = Namespace('monitoring', description='Health and status monitoring')

api.add_namespace(ns_scraper, path='/scraper')
api.add_namespace(ns_management, path='/management')
api.add_namespace(ns_monitoring, path='/monitoring')

# API Models
scraper_config = api.model('ScraperConfig', {
    'csv_path': fields.String(description='CSV file path', default='seminole_property_urls.csv'),
    'start_row': fields.Integer(description='Starting row (auto-calculated if not provided)'),
    'end_row': fields.Integer(description='Ending row (auto-calculated if not provided)'),
    'output_file': fields.String(description='Output file name', default='final_results_Seminole.csv'),
    'chunk_size': fields.Integer(description='Properties per chunk', default=100),
    'progress_file': fields.String(description='Progress file name', default='progress.txt')
})

file_info = api.model('FileInfo', {
    'filename': fields.String(description='File name'),
    'size_bytes': fields.Integer(description='File size in bytes'),
    'size_human': fields.String(description='Human readable file size'),
    'modified': fields.String(description='Last modified timestamp'),
    'download_url': fields.String(description='Direct download URL')
})

download_info = api.model('DownloadInfo', {
    'filename': fields.String(description='File name'),
    'size_bytes': fields.Integer(description='File size in bytes'),
    'size_human': fields.String(description='Human readable file size'),
    'modified': fields.String(description='Last modified timestamp'),
    'download_url': fields.String(description='Download URL'),
    'instructions': fields.String(description='Download instructions'),
    'status': fields.String(description='File status')
})

def upload_to_gcs(local_file_path, blob_name):
    """Upload file to Google Cloud Storage"""
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        blob.upload_from_filename(local_file_path)
        print(f"✅ Uploaded {local_file_path} to gs://{BUCKET_NAME}/{blob_name}")
        return True
    except Exception as e:
        print(f"❌ Error uploading to GCS: {e}")
        return False

def download_from_gcs(blob_name, local_file_path):
    """Download file from Google Cloud Storage"""
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        if blob.exists():
            blob.download_to_filename(local_file_path)
            print(f"✅ Downloaded gs://{BUCKET_NAME}/{blob_name} to {local_file_path}")
            return True
        else:
            print(f"📁 File gs://{BUCKET_NAME}/{blob_name} doesn't exist yet")
            return False
    except Exception as e:
        print(f"❌ Error downloading from GCS: {e}")
        return False

def get_file_size(filepath):
    """Get human readable file size"""
    try:
        size = os.path.getsize(filepath)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    except:
        return "Unknown"

def get_dynamic_defaults(csv_path):
    """Get dynamic defaults based on CSV file size"""
    try:
        df = pd.read_csv(csv_path)
        total_rows = len(df)
        return {
            'total_rows': total_rows,
            'default_start_row': 0,
            'default_end_row': total_rows - 1
        }
    except Exception as e:
        print(f"❌ Error reading CSV file '{csv_path}': {e}")
        return {
            'total_rows': 0,
            'default_start_row': 0,
            'default_end_row': 100  # Fallback
        }

# SCRAPER ENDPOINTS
@ns_scraper.route('/run')
class ScraperRun(Resource):
    @ns_scraper.expect(scraper_config)
    @ns_scraper.doc('run_scraper')
    def post(self):
        """Run the property scraper with configurable parameters"""
        global processing_state
        
        if processing_state["is_running"]:
            return {"status": "error", "message": "Scraper is already running"}, 400
        
        try:
            print(f"🚀 Scraper triggered at {datetime.now()}")
            
            # Get configuration from request JSON
            config = request.get_json() or {}
            
            # Get CSV path first to determine file-based defaults
            csv_path = config.get("csv_path", "seminole_property_urls.csv")
            output_file = config.get("output_file", "final_results_Seminole.csv")
            chunk_size = config.get("chunk_size", 100)
            progress_file = config.get("progress_file", "progress.txt")
            
            # Download CSV file from GCS if needed
            download_from_gcs(csv_path, csv_path)
            
            # Get dynamic defaults
            defaults = get_dynamic_defaults(csv_path)
            
            start_row = config.get("start_row", defaults['default_start_row'])
            end_row = config.get("end_row", defaults['default_end_row'])
            
            print(f"📁 CSV file '{csv_path}' has {defaults['total_rows']} total rows")
            print(f"📋 Configuration: csv_path={csv_path}, start_row={start_row}, end_row={end_row}")
            print(f"📋 Output: {output_file}, chunk_size={chunk_size}")
            
            # Download existing progress and results files from GCS
            download_from_gcs(progress_file, progress_file)
            download_from_gcs(output_file, output_file)
            
            # Update processing state
            processing_state.update({
                "is_running": True,
                "current_task": f"Processing rows {start_row}-{end_row}",
                "start_time": datetime.now().isoformat(),
                "progress": f"Starting...",
                "error": None
            })
            
            # Run scraper in background thread
            def run_scraper_background():
                try:
                    run_scraper(
                        csv_path=csv_path,
                        start_row=start_row,
                        end_row=end_row,
                        output_file=output_file,
                        chunk_size=chunk_size,
                        progress_file=progress_file
                    )
                    
                    # Upload results back to GCS
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    # Upload progress file
                    if os.path.exists(progress_file):
                        upload_to_gcs(progress_file, progress_file)
                        upload_to_gcs(progress_file, f"backups/{progress_file}_{timestamp}")
                    
                    # Upload results file
                    if os.path.exists(output_file):
                        upload_to_gcs(output_file, output_file)
                        upload_to_gcs(output_file, f"backups/{output_file}_{timestamp}")
                    
                    processing_state.update({
                        "is_running": False,
                        "current_task": "Completed",
                        "progress": f"Finished processing rows {start_row}-{end_row}"
                    })
                    
                except Exception as e:
                    processing_state.update({
                        "is_running": False,
                        "current_task": "Failed",
                        "error": str(e)
                    })
            
            thread = threading.Thread(target=run_scraper_background)
            thread.daemon = True
            thread.start()
            
            return {
                "status": "started",
                "message": "Scraper started successfully",
                "timestamp": datetime.now().isoformat(),
                "configuration": {
                    "csv_path": csv_path,
                    "start_row": start_row,
                    "end_row": end_row,
                    "output_file": output_file,
                    "chunk_size": chunk_size,
                    "progress_file": progress_file,
                    "total_rows_in_csv": defaults['total_rows']
                }
            }, 202
            
        except Exception as e:
            processing_state.update({
                "is_running": False,
                "current_task": "Failed",
                "error": str(e)
            })
            print(f"❌ Error in scraper endpoint: {e}")
            return {
                "status": "error", 
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }, 500

# MANAGEMENT ENDPOINTS
@ns_management.route('/files')
class FilesList(Resource):
    @ns_management.marshal_list_with(file_info)
    @ns_management.doc('list_files')
    def get(self):
        """List all available CSV and TXT files with metadata"""
        try:
            files_data = []
            target_extensions = ('.csv', '.txt')
            
            for filename in os.listdir('.'):
                if filename.endswith(target_extensions):
                    try:
                        file_path = os.path.join('.', filename)
                        stat = os.stat(file_path)
                        
                        files_data.append({
                            'filename': filename,
                            'size_bytes': stat.st_size,
                            'size_human': get_file_size(file_path),
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'download_url': f"{request.url_root}api/management/download/{filename}"
                        })
                    except Exception as e:
                        print(f"Error reading file {filename}: {e}")
                        continue
            
            return files_data
            
        except Exception as e:
            return {"error": f"Failed to list files: {str(e)}"}, 500

@ns_management.route('/download-info/<string:filename>')
class DownloadInfo(Resource):
    @ns_management.marshal_with(download_info)
    @ns_management.doc('get_download_info')
    def get(self, filename):
        """Get download information for a specific file (Swagger-friendly)"""
        try:
            if not os.path.exists(filename):
                return {"error": "File not found"}, 404
            
            stat = os.stat(filename)
            download_url = f"{request.url_root}api/management/download/{filename}"
            
            return {
                'filename': filename,
                'size_bytes': stat.st_size,
                'size_human': get_file_size(filename),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'download_url': download_url,
                'instructions': 'Copy the download_url and paste it in your browser to download the file',
                'status': 'ready_for_download'
            }
            
        except Exception as e:
            return {"error": f"Failed to get file info: {str(e)}"}, 500

@ns_management.route('/download/<string:filename>')
class FileDownload(Resource):
    @ns_management.doc('download_file')
    def get(self, filename):
        """Download a specific file directly"""
        try:
            if not os.path.exists(filename):
                return {"error": "File not found"}, 404
                
            return send_file(
                filename,
                as_attachment=True,
                download_name=filename
            )
            
        except Exception as e:
            return {"error": f"Download failed: {str(e)}"}, 500

# MONITORING ENDPOINTS
@ns_monitoring.route('/health')
class HealthCheck(Resource):
    @ns_monitoring.doc('health_check')
    def get(self):
        """Health check with environment validation"""
        try:
            # Check environment variables
            env_status = {
                "BROWSERBASE_API_KEY": "✅ Set" if os.getenv("BROWSERBASE_API_KEY") else "❌ Missing",
                "BROWSERBASE_PROJECT_ID": "✅ Set" if os.getenv("BROWSERBASE_PROJECT_ID") else "❌ Missing",
                "GCS_BUCKET_NAME": "✅ Set" if os.getenv("GCS_BUCKET_NAME") else "❌ Missing"
            }
            
            # Check key files
            csv_file = "seminole_property_urls.csv"
            file_status = {
                csv_file: "✅ Found" if os.path.exists(csv_file) else "❌ Missing"
            }
            
            # Overall status
            all_env_ok = all("✅" in status for status in env_status.values())
            files_ok = all("✅" in status for status in file_status.values())
            overall_healthy = all_env_ok and files_ok
            
            return {
                "status": "healthy" if overall_healthy else "warning",
                "service": "browserbase-scraper-cloud",
                "timestamp": datetime.now().isoformat(),
                "environment": env_status,
                "files": file_status,
                "ready_for_scraping": overall_healthy
            }, 200 if overall_healthy else 503
            
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }, 500

@ns_monitoring.route('/status')
class ProcessingStatus(Resource):
    @ns_monitoring.doc('get_status')
    def get(self):
        """Get current processing status and progress"""
        try:
            global processing_state
            
            status_response = {
                "is_running": processing_state["is_running"],
                "current_task": processing_state["current_task"],
                "start_time": processing_state["start_time"],
                "progress": processing_state["progress"],
                "error": processing_state["error"],
                "timestamp": datetime.now().isoformat()
            }
            
            # Add progress file info if available
            if os.path.exists("progress.txt"):
                try:
                    with open("progress.txt", "r") as f:
                        progress_content = f.read().strip()
                    status_response["progress_file_content"] = progress_content
                except:
                    pass
            
            return status_response
            
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }, 500

# Legacy endpoints for backward compatibility
@app.route("/", methods=["GET", "POST"])
def legacy_run_scraper():
    """Legacy endpoint - redirects to new API structure"""
    if request.method == "GET":
        return jsonify({
            "message": "Welcome to Browserbase Property Scraper API v2.0",
            "swagger_ui": f"{request.url_root}swagger/",
            "new_api_endpoint": f"{request.url_root}api/scraper/run",
            "migration_note": "This endpoint still works but please use the new API structure"
        })
    
    # For POST requests, proxy to new endpoint
    try:
        from werkzeug.test import Client
        from werkzeug.wrappers import Response
        
        # Create test client and forward request
        client = Client(app, Response)
        response = client.post('/api/scraper/run', 
                             json=request.get_json(),
                             headers=dict(request.headers))
        
        return response[0], response[1]
    except Exception as e:
        return jsonify({"error": f"Legacy endpoint error: {str(e)}"}), 500

@app.route("/health", methods=["GET"])
def legacy_health():
    """Legacy health endpoint"""
    return jsonify({"status": "healthy", "service": "browserbase-scraper", "note": "Use /api/monitoring/health for detailed status"}), 200

if __name__ == "__main__":
    print("🔧 Starting Enhanced Browserbase Scraper API for Cloud Run...")
    print(f"📡 Access at: http://localhost:{PORT}")
    print(f"🔗 Swagger UI: http://localhost:{PORT}/swagger/")
    print("📚 Available endpoints:")
    print(f"   • POST  /api/scraper/run                     - Run scraper with custom config")
    print(f"   • GET   /api/management/files                - List available files")
    print(f"   • GET   /api/management/download-info/<file> - Get download info")
    print(f"   • GET   /api/management/download/<file>      - Direct file download")
    print(f"   • GET   /api/monitoring/health               - Health check with env validation")
    print(f"   • GET   /api/monitoring/status               - Processing status")
    print("🎯 Ready for Cloud Run deployment!")
    
    app.run(host="0.0.0.0", port=PORT, debug=False) 