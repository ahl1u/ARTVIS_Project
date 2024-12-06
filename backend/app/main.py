from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .analyzer import PaperAnalyzer
import traceback
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

analyzer = PaperAnalyzer()

@app.post("/analyze-paper")
async def analyze_paper(file: UploadFile):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    try:
        logger.info(f"Processing file: {file.filename}")
        
        contents = await file.read()
        logger.info(f"File size: {len(contents)} bytes")
        
        if len(contents) > 10 * 1024 * 1024: #limit so we don't get something too big
            raise HTTPException(status_code=400, detail="File too large. Please upload a smaller PDF")
            
        logger.info("Extracting text from PDF...")
        text = analyzer.extract_text_from_pdf(contents)
        if not text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from PDF. Please make sure it's not scanned or corrupted")
        logger.info(f"Extracted text length: {len(text)} characters")
            
        logger.info("Extracting topics...")
        topics = analyzer.extract_topics(text)
        if not topics:
            raise HTTPException(status_code=500, detail="Could not extract topics from the paper")
        logger.info(f"Extracted topics: {topics}")
            
        logger.info("Finding related papers...")
        related_papers = analyzer.find_related_papers(topics)
        logger.info(f"Found {len(related_papers)} related papers")
        
        logger.info("Creating graph data...")
        graph_data = analyzer.create_graph_data(
            file.filename,
            topics,
            related_papers
        )
        return graph_data
        
    except Exception as e:
        logger.error("Error processing paper:")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}