# Browserbase Property Scraper - Deployment Guide v2.0

## 🚀 Enhanced Features (v2.0)

✅ **Interactive Swagger UI** for API testing  
✅ **Organized REST API** with proper namespaces  
✅ **Dual Deployment Options** (Local + Cloud Run)  
✅ **Advanced File Management** with download capabilities  
✅ **Real-time Progress Monitoring**  
✅ **Enhanced Error Handling & Validation**  
✅ **Dynamic CSV Processing** with auto-calculated defaults  

---

## 📋 Quick Setup

### **1. Get Your Browserbase API Key**
1. Sign up at [https://www.browserbase.com](https://www.browserbase.com)
2. Go to Dashboard → Settings → API
3. Copy your API key and project ID

### **2. Environment Variables**
Create a `.env` file or set environment variables:
```bash
export BROWSERBASE_API_KEY=your_api_key_here
export BROWSERBASE_PROJECT_ID=your_project_id_here
# For Cloud Run only:
export GCS_BUCKET_NAME=your-bucket-name
```

---

## 🖥️ Local Development

### **Option 1: Interactive Development Server (Recommended)**
```bash
# Install dependencies
pip install -r requirements.txt

# Start the enhanced API with Swagger UI
python swagger_api.py

# Access Swagger UI: http://localhost:5000/swagger/
```

### **Available Endpoints (Local):**
- 🎯 **Swagger UI**: `http://localhost:5000/swagger/`
- 📡 **Health Check**: `GET /api/monitoring/health`
- 🚀 **Run Scraper**: `POST /api/scraper/run`
- 📁 **List Files**: `GET /api/management/files`
- 📥 **Download**: `GET /api/management/download/<filename>`

---

## ☁️ Cloud Run Deployment

### **Option 1: Automated Deployment**
```bash
# Build and deploy (requires gcloud CLI)
chmod +x deploy.sh
./deploy.sh
```

### **Option 2: Manual Docker Deployment**
```bash
# Build Docker image
docker build -t browserbase-scraper:v2 .

# Test locally first (optional)
docker run -p 8080:8080 \
  -e BROWSERBASE_API_KEY=your_key \
  -e BROWSERBASE_PROJECT_ID=your_project_id \
  -e GCS_BUCKET_NAME=your_bucket \
  browserbase-scraper:v2

# Access: http://localhost:8080/swagger/

# Deploy to Google Cloud Run
gcloud run deploy browserbase-scraper \
  --image browserbase-scraper:v2 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars BROWSERBASE_API_KEY=your_key,BROWSERBASE_PROJECT_ID=your_project_id,GCS_BUCKET_NAME=your_bucket
```

### **Cloud Run Endpoints:**
- 🎯 **Swagger UI**: `https://your-service-url/swagger/`
- 📡 **Health Check**: `GET /api/monitoring/health`
- 🚀 **Run Scraper**: `POST /api/scraper/run`
- 📁 **File Management**: `GET /api/management/*`

---

## 📊 API Usage Examples

### **1. Health Check**
```bash
curl https://your-service-url/api/monitoring/health
```

### **2. Start Property Scraping**
```bash
curl -X POST https://your-service-url/api/scraper/run \
  -H "Content-Type: application/json" \
  -d '{
    "start_row": 0,
    "end_row": 100,
    "chunk_size": 50,
    "output_file": "test_results.csv"
  }'
```

### **3. Monitor Progress**
```bash
curl https://your-service-url/api/monitoring/status
```

### **4. Download Results**
```bash
curl -O https://your-service-url/api/management/download/final_results_Seminole.csv
```

---

## ⚙️ Configuration Options

### **Scraper Configuration (POST /api/scraper/run)**
```json
{
  "csv_path": "seminole_property_urls.csv",       // Input CSV file
  "start_row": 0,                                 // Starting row (auto-calculated)
  "end_row": 29695,                              // Ending row (auto-calculated)
  "output_file": "final_results_Seminole.csv",   // Output file name
  "chunk_size": 100,                             // Properties per batch
  "progress_file": "progress.txt"                // Progress tracking file
}
```

### **Dynamic Defaults**
- `start_row` and `end_row` are automatically calculated from CSV file size
- For 29,696 property CSV: defaults to `start_row: 0, end_row: 29695`
- Manual override available for custom ranges

---

## 📁 File Structure

### **Required Files:**
```
├── main.py                    # Cloud Run API (enhanced)
├── swagger_api.py             # Local development API  
├── browserbase_scraper.py     # Core scraper logic
├── scrape_single_property.py  # Property extraction
├── scrape_batch.py           # Batch processing
├── requirements.txt          # Dependencies
├── Dockerfile               # Container config
├── deploy.sh                # Deployment script
└── seminole_property_urls.csv # Input data (29,696 properties)
```

### **Output Files:**
```
├── final_results_Seminole.csv # Scraped property data
├── progress.txt              # Processing progress
└── backups/                  # GCS timestamped backups
```

---

## 🔧 Advanced Configuration

### **For Large Scale Processing:**
```json
{
  "start_row": 0,
  "end_row": 5000,     // Process in chunks
  "chunk_size": 200,   // Larger batches for efficiency
  "output_file": "chunk_1_results.csv"
}
```

### **For Testing:**
```json
{
  "start_row": 0,
  "end_row": 10,       // Small test batch
  "chunk_size": 5,     // Small chunks
  "output_file": "test_results.csv"
}
```

---

## 🛠️ Troubleshooting

### **Local Development Issues:**
- **Port conflicts**: Use different ports (`python swagger_api.py` uses 5000)
- **Missing dependencies**: `pip install -r requirements.txt`
- **CSV not found**: Ensure `seminole_property_urls.csv` is in project root

### **Cloud Run Issues:**
- **Environment variables**: Check `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`, `GCS_BUCKET_NAME`
- **GCS permissions**: Ensure service account has Storage Admin role
- **Timeout**: Reduce `chunk_size` for faster processing
- **Memory**: Increase Cloud Run memory allocation for large batches

### **Docker Issues:**
- **Build fails**: Ensure all files are copied (`COPY . .` in Dockerfile)
- **Port conflicts**: Use different ports (`-p 8081:8080`)
- **Environment**: Set all required environment variables

---

## 📈 Performance Optimization

### **Recommended Settings:**
- **Small batches (1-100 properties)**: `chunk_size: 10-25`
- **Medium batches (100-1000 properties)**: `chunk_size: 50-100`  
- **Large batches (1000+ properties)**: `chunk_size: 100-200`

### **Cloud Run Scaling:**
```bash
gcloud run services update browserbase-scraper \
  --memory 2Gi \
  --cpu 2 \
  --max-instances 10 \
  --concurrency 1000
```

---

## 🚀 What's New in v2.0

### **Enhanced API Structure:**
- ✅ **Swagger UI** for interactive testing
- ✅ **Organized namespaces** (scraper, management, monitoring)
- ✅ **Better error handling** with detailed responses
- ✅ **Real-time status** monitoring

### **Improved File Management:**
- ✅ **List all files** with metadata
- ✅ **Direct downloads** from API
- ✅ **Progress tracking** with real-time updates
- ✅ **GCS integration** for cloud persistence

### **Developer Experience:**
- ✅ **Local development server** (`swagger_api.py`)
- ✅ **Cloud production server** (`main.py`)
- ✅ **Docker support** with optimized builds
- ✅ **Automated deployment** scripts

---

## 📞 Support

For issues or questions:
1. Check the **Swagger UI** documentation at `/swagger/`
2. Use the **health endpoint** to verify configuration
3. Monitor **processing status** via `/api/monitoring/status`
4. Review **Docker logs** for detailed error information

**Happy scraping! 🎯** 