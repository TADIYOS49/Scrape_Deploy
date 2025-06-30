#!/usr/bin/env python3
"""
🚀 MAIN API - Browserbase Property Scraper with Swagger UI
Complete interactive API with full documentation and testing interface

This is the primary API file for production and development use.
Features:
- Interactive Swagger UI at /swagger/
- Complete REST API with all endpoints
- Dynamic CSV file detection and smart defaults
- File management (list & download)
- Health monitoring and status tracking
"""

import os
import sys
from datetime import datetime
from flask import Flask, request
from flask_restx import Api, Resource, fields, Namespace
from browserbase_scraper import main as run_scraper

# Initialize Flask app
app = Flask(__name__)

# Configure Swagger UI
api = Api(
    app,
    version='1.0.0',
    title='Browserbase Property Scraper API',
    description='Interactive API for scraping property data using Browserbase cloud browsers',
    doc='/swagger/',  # Swagger UI will be available at /swagger/
    prefix='/api'
)

# Create namespaces for different API sections
scraper_ns = Namespace('scraper', description='Property scraping operations')
management_ns = Namespace('management', description='File and system management')
monitoring_ns = Namespace('monitoring', description='Health and status monitoring')

api.add_namespace(scraper_ns)
api.add_namespace(management_ns)
api.add_namespace(monitoring_ns)

# Define request/response models for Swagger documentation
scraper_config_model = api.model('ScraperConfig', {
    'csv_path': fields.String(description='Path to CSV file with property URLs', default='seminole_property_urls.csv', example='seminole_property_urls.csv'),
    'start_row': fields.Integer(description='Starting row number (default: 0)', example=0),
    'end_row': fields.Integer(description='Ending row number (default: last row)', example=10),
    'output_file': fields.String(description='Output CSV filename', default='final_results_Seminole.csv', example='final_results_Seminole.csv'),
    'chunk_size': fields.Integer(description='Properties per chunk', default=5, example=5),
    'progress_file': fields.String(description='Progress tracking filename', default='progress.txt', example='progress.txt')
})

scraper_response_model = api.model('ScraperResponse', {
    'status': fields.String(description='Operation status', example='success'),
    'message': fields.String(description='Status message', example='Scraper completed successfully'),
    'timestamp': fields.String(description='Completion timestamp', example='2025-06-28T09:15:18.255476'),
    'configuration': fields.Nested(scraper_config_model, description='Configuration used')
})

health_response_model = api.model('HealthResponse', {
    'status': fields.String(description='Health status', example='healthy'),
    'service': fields.String(description='Service name', example='browserbase-scraper-swagger'),
    'environment_vars': fields.Raw(description='Environment variables status')
})

status_response_model = api.model('StatusResponse', {
    'timestamp': fields.String(description='Current timestamp', example='2025-06-28T09:15:18.255476'),
    'last_processed_row': fields.String(description='Last processed row info', example='Last processed row: 102'),
    'results_file_size': fields.String(description='Results file size', example='1334 bytes')
})

file_info_model = api.model('FileInfo', {
    'name': fields.String(description='File name', example='final_results_Seminole.csv'),
    'size': fields.Integer(description='File size in bytes', example=1334),
    'modified': fields.String(description='Last modified timestamp', example='2025-06-28T09:15:18.255476'),
    'type': fields.String(description='File type', example='local_file')
})

files_response_model = api.model('FilesResponse', {
    'files': fields.List(fields.Nested(file_info_model), description='List of files'),
    'location': fields.String(description='Storage location', example='local_directory'),
    'total_files': fields.Integer(description='Total number of files', example=4),
    'timestamp': fields.String(description='Current timestamp'),
    'note': fields.String(description='Additional information')
})

error_response_model = api.model('ErrorResponse', {
    'status': fields.String(description='Error status', example='error'),
    'message': fields.String(description='Error message', example='Could not read CSV file'),
    'timestamp': fields.String(description='Error timestamp')
})

download_info_model = api.model('DownloadInfo', {
    'filename': fields.String(description='Name of the file', example='final_results_Seminole.csv'),
    'size_bytes': fields.Integer(description='File size in bytes', example=1334),
    'size_human': fields.String(description='Human-readable file size', example='1.3 KB'),
    'modified': fields.String(description='Last modified timestamp', example='2025-06-28T09:15:08.253639'),
    'download_url': fields.String(description='Direct download URL', example='http://localhost:5000/api/management/download/final_results_Seminole.csv'),
    'instructions': fields.String(description='How to download', example='Copy the download_url and paste it in your browser to download the file'),
    'curl_command': fields.String(description='Curl command for download', example='curl -O http://localhost:5000/api/management/download/final_results_Seminole.csv'),
    'status': fields.String(description='Download status', example='ready_for_download')
})

# Scraper endpoints
@scraper_ns.route('/run')
class RunScraper(Resource):
    @scraper_ns.doc('run_scraper')
    @scraper_ns.expect(scraper_config_model, validate=False)
    @scraper_ns.marshal_with(scraper_response_model, code=200)
    @scraper_ns.marshal_with(error_response_model, code=400)
    def post(self):
        """Run the property scraper with configurable parameters"""
        try:
            # Get configuration from request JSON or use defaults
            config = request.get_json() or {}
            
            # Get CSV path first to determine file-based defaults
            csv_path = config.get("csv_path", "seminole_property_urls.csv")
            output_file = config.get("output_file", "final_results_Seminole.csv")
            chunk_size = config.get("chunk_size", 5)  # Smaller for Swagger testing
            progress_file = config.get("progress_file", "progress.txt")
            
            # Determine dynamic defaults based on CSV file
            try:
                import pandas as pd
                df = pd.read_csv(csv_path)
                total_rows = len(df)
                
                # Set defaults based on actual CSV file
                default_start_row = 0
                default_end_row = min(total_rows - 1, 10)  # Limit for Swagger testing
                
                start_row = config.get("start_row", default_start_row)
                end_row = config.get("end_row", default_end_row)
                
                print(f"📁 CSV file '{csv_path}' has {total_rows} total rows")
                print(f"📋 Configuration: csv_path={csv_path}, start_row={start_row}, end_row={end_row}")
                print(f"🧪 Swagger testing: Limited to {end_row - start_row + 1} rows for faster testing")
                
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Could not read CSV file '{csv_path}': {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }, 400
            
            # Run the scraper with custom configuration
            run_scraper(
                csv_path=csv_path,
                start_row=start_row,
                end_row=end_row,
                output_file=output_file,
                chunk_size=chunk_size,
                progress_file=progress_file
            )
            
            return {
                "status": "success",
                "message": "Scraper completed successfully (Swagger test mode)",
                "timestamp": datetime.now().isoformat(),
                "configuration": {
                    "csv_path": csv_path,
                    "start_row": start_row,
                    "end_row": end_row,
                    "output_file": output_file,
                    "chunk_size": chunk_size,
                    "progress_file": progress_file
                }
            }, 200
            
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }, 500

# Management endpoints
@management_ns.route('/files')
class ListFiles(Resource):
    @management_ns.doc('list_files')
    @management_ns.marshal_with(files_response_model, code=200)
    def get(self):
        """List all local files (CSV, TXT)"""
        try:
            files = []
            for filename in os.listdir("."):
                if filename.endswith(('.csv', '.txt')):
                    stat = os.stat(filename)
                    files.append({
                        "name": filename,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "type": "local_file"
                    })
            
            return {
                "files": files,
                "location": "local_directory",
                "total_files": len(files),
                "timestamp": datetime.now().isoformat(),
                "note": "This is the Swagger test version - shows files in current directory"
            }, 200
            
        except Exception as e:
            return {"error": str(e)}, 500

@management_ns.route('/download-info/<string:filename>')
class GetDownloadInfo(Resource):
    @management_ns.doc('get_download_info')
    @management_ns.param('filename', 'Name of the file to get download info for', required=True)
    @management_ns.response(200, 'Success', download_info_model)
    @management_ns.response(400, 'Bad Request', error_response_model)
    @management_ns.response(404, 'Not Found', error_response_model)
    def get(self, filename):
        """Get download information for a file (Swagger-friendly)
        
        Returns JSON with file info and download URL that you can copy and paste.
        Perfect for use in Swagger UI!
        """
        try:
            import os
            from flask import request
            
            # Security check: only allow CSV and TXT files
            if not filename.endswith(('.csv', '.txt')):
                return {"error": "Only CSV and TXT files are allowed for download"}, 400
            
            # Check if file exists
            if not os.path.exists(filename):
                return {"error": f"File '{filename}' not found"}, 404
            
            # Get file info
            file_stat = os.stat(filename)
            base_url = request.url_root.rstrip('/')
            
            return {
                "filename": filename,
                "size_bytes": file_stat.st_size,
                "size_human": f"{file_stat.st_size / 1024:.1f} KB" if file_stat.st_size > 1024 else f"{file_stat.st_size} bytes",
                "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                "download_url": f"{base_url}/api/management/download/{filename}",
                "instructions": "Copy the download_url and paste it in your browser to download the file",
                "curl_command": f"curl -O {base_url}/api/management/download/{filename}",
                "status": "ready_for_download"
            }, 200
            
        except Exception as e:
            return {"error": f"Error getting file info: {str(e)}"}, 500

@management_ns.route('/download/<string:filename>')
class DownloadFile(Resource):
    @management_ns.doc('download_file')
    @management_ns.param('filename', 'Name of the file to download', required=True)
    def get(self, filename):
        """Direct file download (use download-info endpoint for Swagger UI)
        
        This endpoint returns the actual file. For Swagger UI testing, 
        use /api/management/download-info/<filename> instead.
        """
        try:
            from flask import send_file, abort
            import os
            
            # Security check: only allow CSV and TXT files
            if not filename.endswith(('.csv', '.txt')):
                return {"error": "Only CSV and TXT files are allowed for download"}, 400
            
            # Check if file exists
            if not os.path.exists(filename):
                return {"error": f"File '{filename}' not found"}, 404
            
            # Send file for download
            return send_file(
                filename,
                as_attachment=True,
                download_name=filename
            )
            
        except Exception as e:
            return {"error": f"Error downloading file: {str(e)}"}, 500

# Monitoring endpoints
@monitoring_ns.route('/health')
class HealthCheck(Resource):
    @monitoring_ns.doc('health_check')
    @monitoring_ns.marshal_with(health_response_model, code=200)
    def get(self):
        """Health check endpoint with environment validation"""
        return {
            "status": "healthy",
            "service": "browserbase-scraper-swagger",
            "environment_vars": {
                "BROWSERBASE_API_KEY": "✅ Set" if os.getenv("BROWSERBASE_API_KEY") else "❌ Missing",
                "BROWSERBASE_PROJECT_ID": "✅ Set" if os.getenv("BROWSERBASE_PROJECT_ID") else "❌ Missing"
            }
        }, 200

@monitoring_ns.route('/status')
class GetStatus(Resource):
    @monitoring_ns.doc('get_status')
    @monitoring_ns.marshal_with(status_response_model, code=200)
    def get(self):
        """Get current processing status and file information"""
        try:
            status_info = {"timestamp": datetime.now().isoformat()}
            
            # Read progress if exists
            if os.path.exists("progress.txt"):
                with open("progress.txt", "r") as f:
                    content = f.read().strip()
                    status_info["last_processed_row"] = content
            else:
                status_info["last_processed_row"] = "No progress file found"
            
            # Check if results file exists
            if os.path.exists("final_results_Seminole.csv"):
                file_size = os.path.getsize("final_results_Seminole.csv")
                status_info["results_file_size"] = f"{file_size} bytes"
            else:
                status_info["results_file_size"] = "No results file found"
                
            return status_info, 200
            
        except Exception as e:
            return {"error": str(e)}, 500

# Root redirect to Swagger
@app.route('/')
def redirect_to_swagger():
    """Redirect root to Swagger UI"""
    return f'''
    <html>
        <head><title>Browserbase Property Scraper API</title></head>
        <body style="font-family: Arial, sans-serif; margin: 40px;">
            <h1>🚀 Browserbase Property Scraper API</h1>
            <p>Welcome to the interactive API documentation!</p>
            <h2>📚 Available Interfaces:</h2>
            <ul>
                <li><a href="/swagger/" style="color: #007bff; text-decoration: none;">
                    <strong>🔧 Swagger UI</strong></a> - Interactive API testing interface</li>
                <li><a href="/api/scraper/run" style="color: #28a745; text-decoration: none;">
                    <strong>🏃 Run Scraper</strong></a> - POST endpoint for running scraper</li>
                                 <li><a href="/api/management/files" style="color: #17a2b8; text-decoration: none;">
                     <strong>📁 List Files</strong></a> - GET endpoint for file management</li>
                 <li><a href="/api/management/download-info/final_results_Seminole.csv" style="color: #28a745; text-decoration: none;">
                     <strong>📋 Download Info</strong></a> - GET download info (Swagger-friendly)</li>
                 <li><a href="/api/management/download/final_results_Seminole.csv" style="color: #dc3545; text-decoration: none;">
                     <strong>⬇️ Direct Download</strong></a> - Direct file download</li>
                <li><a href="/api/monitoring/health" style="color: #ffc107; text-decoration: none;">
                    <strong>💚 Health Check</strong></a> - GET endpoint for health status</li>
                <li><a href="/api/monitoring/status" style="color: #6c757d; text-decoration: none;">
                    <strong>📊 Status</strong></a> - GET endpoint for processing status</li>
            </ul>
                         <h2>🎯 Quick Start:</h2>
             <ol>
                 <li>Visit <a href="/swagger/" style="color: #007bff;"><strong>Swagger UI</strong></a></li>
                 <li>Test the <strong>/api/scraper/run</strong> endpoint</li>
                 <li>Use the "Try it out" button to customize parameters</li>
                 <li>Monitor progress with <strong>/api/monitoring/status</strong></li>
                 <li>List files with <strong>/api/management/files</strong></li>
                 <li>Get download info with <strong>/api/management/download-info/&lt;filename&gt;</strong></li>
                 <li>Copy the download_url from the response and paste in browser</li>
             </ol>
            <p style="margin-top: 30px; color: #666;">
                🧪 <strong>Swagger Test Mode:</strong> Limited to first 10 rows for faster testing
            </p>
        </body>
    </html>
    '''

if __name__ == "__main__":
    print("🔧 Starting Swagger-enabled Flask API...")
    print("📡 Access at: http://localhost:5000")
    print("🔗 Swagger UI: http://localhost:5000/swagger/")
    print("📚 Available endpoints:")
    print("   • POST  /api/scraper/run                     - Run scraper with custom config")
    print("   • GET   /api/management/files                - List available files")
    print("   • GET   /api/management/download-info/<file> - Get download info (Swagger-friendly)")
    print("   • GET   /api/management/download/<file>      - Direct file download")
    print("   • GET   /api/monitoring/health               - Health check")
    print("   • GET   /api/monitoring/status               - Processing status")
    print("\n🎯 Open http://localhost:5000/swagger/ for interactive testing!")
    
    app.run(host="0.0.0.0", port=5000, debug=True) 