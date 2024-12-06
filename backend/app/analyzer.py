import os
import openai
import requests
import json
import PyPDF2
import io
from dotenv import load_dotenv
import urllib.parse
import xml.etree.ElementTree as ET
import logging
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# configure logging to display information and error messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# load environment variables from a .env file
load_dotenv()


app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "your-app.vercel.app",  # Replace with your actual Vercel domain
        "http://localhost:3000"  # Keep local development working
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PaperAnalyzer:
    def __init__(self):
        # retrieve openai api key and organization id from environment variables
        api_key = os.getenv('OPENAI_API_KEY')
        org_id = os.getenv('OPENAI_ORG_ID')
        
        # check if the api key is available, log an error and raise an exception if not
        if not api_key:
            logger.error("openai api key not found in environment variables")
            raise ValueError("openai api key not found")
        
        # log the initialization of the openai client with the organization id if provided
        logger.info(f"initializing openai client with organization: {org_id if org_id else 'none'}")
        
        # initialize the openai client with the api key and organization id
        self.client = openai.OpenAI(
            api_key=api_key,
            organization=org_id,
            base_url="https://api.openai.com/v1"
        )

        # set the arxiv api endpoint for querying related papers
        self.arxiv_api = "http://export.arxiv.org/api/query"
        # specify the openai model to use for topic extraction
        self.model = "gpt-3.5-turbo"
        
        # log successful initialization of the PaperAnalyzer
        logger.info("paperanalyzer initialized successfully")

    def extract_text_from_pdf(self, pdf_file):
        """
        extract text from the first 10 pages of a pdf file
        """
        try:
            # read the pdf file using PyPDF2
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file))
            text = ""
            # limit the extraction to a maximum of 10 pages
            max_pages = min(len(pdf_reader.pages), 10)
            for i, page in enumerate(pdf_reader.pages[:max_pages]):
                try:
                    # extract text from the current page
                    page_text = page.extract_text()
                    text += page_text
                    # log the number of characters extracted from the current page
                    logger.debug(f"extracted {len(page_text)} characters from page {i+1}")
                except Exception as e:
                    # log any errors encountered while extracting text from a page
                    logger.error(f"error extracting text from page {i+1}: {str(e)}")
            
            # check if any text was extracted, raise an error if not
            if not text.strip():
                raise ValueError("no text could be extracted from the pdf")
                
            # log the total number of characters extracted from the pdf
            logger.info(f"successfully extracted {len(text)} characters from pdf")
            return text
        except Exception as e:
            # log any errors encountered during the text extraction process
            logger.error(f"error in extract_text_from_pdf: {str(e)}")
            raise

    def extract_topics(self, text):
        """
        use openai to extract main research topics and their subtopics from the provided text
        """
        try:
            # truncate the text to the first 4000 characters to stay within model limits
            truncated_text = text[:4000]
            # log the model being used and the length of the text for analysis
            logger.info(f"using model: {self.model}")
            logger.info(f"text length for analysis: {len(truncated_text)} characters")
            
            # create a chat completion request to the openai API with a system prompt for topic extraction
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """extract exactly 5 main research topics and their subtopics from the text.
        return a json array where each main topic has a 'topic', 'importance', and a 'subtopics' field.
        each 'subtopics' field should be an array of subtopic objects with 'topic' and 'importance'.
        keep topics short and precise, but do not be afraid to have a decent amount of length. Keep in mind that each topic should be relevant to the core argument and paper, not just a specific section of the paper. each main topic should have up to 3 subtopics.
        example format:
        [
            {
                "topic": "neural networks",
                "importance": 9,
                "subtopics": [
                    {"topic": "convolutional neural networks in image processing", "importance": 8},
                    {"topic": "recurrent neural networks in speech recognition", "importance": 7}
                ]
            },
            {
                "topic": "computer vision for autonomous driving",
                "importance": 7,
                "subtopics": [
                    {"topic": "image classification for object detection", "importance": 6}
                ]
            }
        ]"""
                    },
                    {
                        "role": "user",
                        "content": truncated_text
                    }
                ],
                temperature=0.3
            )
            
            # retrieve the content of the response from openai
            result = response.choices[0].message.content
            logger.info(f"openai response: {result}")
            
            # strip any leading or trailing whitespace from the result
            result = result.strip()
            # parse the json response to get the list of topics
            topics = json.loads(result)
            
            # ensure that the parsed result is a list
            if not isinstance(topics, list):
                raise ValueError("openai did not return a list of topics")
                
            # log the successfully extracted topics
            logger.info(f"successfully extracted topics: {topics}")
            return topics
            
        except Exception as e:
            # log any errors encountered during topic extraction
            logger.error(f"error in extract_topics: {str(e)}")
            # log the openai response if available
            logger.error(f"openai api response: {response.choices[0].message.content if 'response' in locals() else 'no response'}")
            raise

    def find_related_papers(self, topics):
        """
        search arxiv for papers related to the extracted topics and their subtopics
        """
        related_papers = []
        # gather all main topics
        all_topics = [topic["topic"] for topic in topics]
        # extend the list with all subtopics
        for topic in topics:
            all_topics.extend([subtopic["topic"] for subtopic in topic.get('subtopics', [])])

        # log all topics that will be used for searching related papers
        logger.info(f"all topics to search: {all_topics}")

        for topic_name in all_topics:
            try:
                # encode the topic name for use in a URL query
                query = urllib.parse.quote(topic_name)
                # send a GET request to the arxiv API with the encoded query, maxim results to 3
                response = requests.get(
                    f"{self.arxiv_api}?search_query=all:{query}&start=0&max_results=3",
                    timeout=10
                )
                
                # check if the request was successful
                if response.status_code == 200:
                    # define the namespaces used in the arxiv API response
                    ns = {
                        'atom': 'http://www.w3.org/2005/Atom',
                        'arxiv': 'http://arxiv.org/schemas/atom'
                    }
                    
                    # parse the XML response from arxiv
                    root = ET.fromstring(response.text)
                    # find all entry elements in the XML
                    entries = root.findall('.//atom:entry', ns)
                    
                    # xml debg
                    logger.info(f"raw xml response: {response.text[:1000]}")
                    logger.info(f"number of entries found: {len(entries)}")
                    
                    for entry in entries:
                        try:
                            # extract the paper id from the entry
                            paper_id_elem = entry.find('atom:id', ns)
                            paper_id = paper_id_elem.text.split('/')[-1] if paper_id_elem is not None else "id not found"
                            
                            # extract the paper title from the entry
                            paper_title_elem = entry.find('atom:title', ns)
                            paper_title = paper_title_elem.text.strip() if paper_title_elem is not None else "title not found"
                            
                            # extract the summary or abstract from the entry
                            summary_elem = entry.find('atom:summary', ns)
                            summary = summary_elem.text.strip() if summary_elem is not None else "no abstract available"
                            
                            # extract the published date from the entry
                            published_elem = entry.find('atom:published', ns)
                            published = published_elem.text.split('T')[0] if published_elem is not None else "date not available"
                            
                            # extract the list of authors from the entry
                            authors = []
                            author_elements = entry.findall('atom:author', ns)
                            for author in author_elements:
                                name_elem = author.find('atom:name', ns)
                                if name_elem is not None:
                                    authors.append(name_elem.text.strip())
                            
                            # log the extracted details of the paper
                            logger.info(f"found paper id: {paper_id}")
                            logger.info(f"found title: {paper_title}")
                            logger.info(f"found summary: {summary[:100]}...")
                            logger.info(f"found published: {published}")
                            logger.info(f"found authors: {authors}")
                            
                            # add the extracted paper details to the related_papers list
                            related_papers.append({
                                "id": paper_id,
                                "title": paper_title,
                                "summary": summary,
                                "published": published,
                                "authors": authors,
                                "topic": topic_name
                            })
                            
                        except Exception as e:
                            # log any errors encountered while processing an entry
                            logger.error(f"error processing entry: {str(e)}")
                            # log the problematic entry in string format
                            logger.error(f"entry that caused error: {ET.tostring(entry, encoding='unicode')}")
                            continue


            except Exception as e:
                # log any errors encountered while finding papers for a specific topic
                logger.error(f"error finding papers for topic {topic_name}: {str(e)}")
                continue

        # return the list of related papers found
        return related_papers

    def create_graph_data(self, main_paper_title, topics, related_papers):
        """
        Create graph data structure with nodes and links based on the main paper, extracted topics, and subtopics.
        """
        try:
            # Create a shortened version of the main paper title for display purposes
            short_title = main_paper_title[:50] + "..." if len(main_paper_title) > 50 else main_paper_title
            
            # Initialize the nodes list with the main paper node
            nodes = [{
                "id": "main",
                "name": short_title,
                "val": 20,
                "group": "main"
            }]
            
            # Initialize the links list to connect main paper to topics
            links = []
            
            # Add nodes and links for each main topic and their subtopics
            for topic in topics:
                main_topic_id = f"topic_{topic['topic']}"
                nodes.append({
                    "id": main_topic_id,
                    "name": topic["topic"],
                    "val": topic["importance"] * 2,
                    "group": "topic"
                })
                links.append({
                    "source": "main",
                    "target": main_topic_id,
                    "value": topic["importance"]
                })
                
                # Process subtopics if they exist
                for subtopic in topic.get('subtopics', []):
                    subtopic_id = f"subtopic_{main_topic_id}_{subtopic['topic']}"
                    nodes.append({
                        "id": subtopic_id,
                        "name": subtopic["topic"],
                        "val": subtopic["importance"],
                        "group": "subtopic"
                    })
                    links.append({
                        "source": main_topic_id,
                        "target": subtopic_id,
                        "value": subtopic["importance"]
                    })

            # Log successful creation of graph data
            logger.info(f"Successfully created graph data with {len(nodes)} nodes and {len(links)} links")
            return {
                "nodes": nodes,
                "links": links
            }, related_papers
                
        except Exception as e:
            # Log any errors encountered while creating graph data
            logger.error(f"Error in create_graph_data: {str(e)}")
            raise

@app.post("/analyze-paper")
async def analyze_paper(file: UploadFile):
    """
    endpoint to analyze an uploaded pdf paper, extract topics, find related papers, and return graph data
    """
    try:
        # check if the uploaded file is a pdf, raise an error if not
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="only pdf files are supported")

        # read the content of the uploaded file
        file_content = await file.read()
        # initialize the PaperAnalyzer
        analyzer = PaperAnalyzer()
        
        # extract text from the pdf content
        analyzer.extract_text_from_pdf(file_content)
        
        # extract topics from the extracted text
        analyzer.extract_topics(text)
        
        # log all topics that will be used for searching related papers
        logger.info(f"all topics to search: {all_topics}")

        # find related papers based on all collected topics
        analyzer.find_related_papers(topics)
    except Exception as e:
        # log any errors encountered during the analysis process
        logger.error(f"error processing paper: {str(e)}")
        logger.error("traceback:", exc_info=True)
        # return an internal server error with the error details
        raise HTTPException(status_code=500, detail=str(e))