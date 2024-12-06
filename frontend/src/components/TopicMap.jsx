import { useState, useRef, useEffect } from 'react';
import { ForceGraph2D } from 'react-force-graph';
import { forceCenter, forceCollide } from 'd3-force';
import { Upload, X, ChevronRight } from 'lucide-react';
import PropTypes from 'prop-types';

// define the shape for paper prop types
const PaperShape = PropTypes.shape({
  id: PropTypes.string,         
  title: PropTypes.string,   
  authors: PropTypes.arrayOf(PropTypes.string),
  summary: PropTypes.string, 
  published: PropTypes.string, 
  topic: PropTypes.string 
});
// component to display individual paper details
const Paper = ({ paper }) => (
  <div className="bg-gray-50 rounded-lg p-4">
    <h4 className="font-medium mb-2">{paper.title}</h4>
    <p className="text-sm text-gray-600 mb-2">
      authors: {Array.isArray(paper.authors) ? paper.authors.join(', ') : 'unknown'}
    </p>
    <p className="text-sm text-gray-500 mb-2">
      published: {paper.published || 'unknown date'}
    </p>
    <details className="text-sm">
      <summary className="cursor-pointer hover:text-blue-600">
        show abstract
      </summary>
      <p className="mt-2 text-gray-700 whitespace-pre-wrap">
        {paper.summary || 'no abstract available'}
      </p>
    </details>
    <a
      href={`https://arxiv.org/abs/${paper.id}`}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center mt-2 text-blue-600 hover:text-blue-800"
    >
      view on arxiv <ChevronRight className="w-4 h-4 ml-1" />
    </a>
  </div>
);

Paper.propTypes = {
  paper: PaperShape.isRequired
};

// component for the side panel displaying node details and related papers
const SidePanel = ({ node, papers, onClose }) => {

  // return nothing if no node is selected
  if (!node) return null;

  // filter and prepare papers related to the selected node's topic
  const relevantPapers = papers
    .filter(p => p && p.topic === node?.name)
    .map(p => ({
      ...p,
      authors: p.authors || [],
      summary: p.summary || '',
      published: p.published || '',
      title: p.title || '',
      id: p.id || ''
    }));

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-white shadow-lg overflow-y-auto">
      <div className="sticky top-0 bg-white z-10 p-6 border-b">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">{node.name}</h2>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-full"
            aria-label="close panel"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        {node.group === 'topic' && (
          <div className="mt-4">
            <h3 className="font-semibold mb-2">importance score</h3>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div 
                className="bg-blue-600 h-2.5 rounded-full transition-all duration-300" 
                style={{ width: `${(node.val / 20) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {(node.group === 'topic' || node.group === 'subtopic') && (
  <div className="p-6">
    <h3 className="font-semibold mb-4">related papers</h3>
    {relevantPapers.length > 0 ? (
      <div className="space-y-4">
        {relevantPapers.map((paper) => (
          <Paper key={paper.id} paper={paper} />
        ))}
      </div>
    ) : (
      <p className="text-gray-500 text-center py-8">no related papers found</p>
    )}
  </div>
)}
    </div>
  );
};

SidePanel.propTypes = {
  node: PropTypes.shape({
    name: PropTypes.string.isRequired,
    group: PropTypes.oneOf(['main', 'topic', 'subtopic']).isRequired,
    val: PropTypes.number.isRequired,
  }),
  papers: PropTypes.arrayOf(PaperShape).isRequired,
  onClose: PropTypes.func.isRequired,
};

SidePanel.defaultProps = {
  node: null,
};

// main component to display the topic map with force-directed graph
const TopicMap = () => {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [relatedPapers, setRelatedPapers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const fgRef = useRef();

  // store initial view parameters for resetting the graph view
  const initialView = useRef({
    zoom: 0.7,
    x: 0,
    y: 0,
  });

  // configure force simulation when graph data changes
  useEffect(() => {
    if (fgRef.current && graphData.nodes.length > 0) {
      // Set charge force to repel nodes
      fgRef.current.d3Force('charge').strength(-300);
      
      // Dynamically set link distance based on node groups
      fgRef.current.d3Force('link').distance(link => {
        const sourceGroup = link.source.group;
        const targetGroup = link.target.group;
      
        if (
          (sourceGroup === 'main' && targetGroup === 'topic') ||
          (sourceGroup === 'topic' && targetGroup === 'main')
        ) {
          return 200; // Longer distance for main topics
        } else if (
          (sourceGroup === 'topic' && targetGroup === 'subtopic') ||
          (sourceGroup === 'subtopic' && targetGroup === 'topic')
        ) {
          return 50; // **Even shorter distance for subtopics**
        }
        return 150; // Default distance for other links
      }).strength(0.1); // Maintain the existing link strength      
  
      // Add collision force to prevent node overlap
      fgRef.current.d3Force('collision', forceCollide(15));  
      // Center the graph
      fgRef.current.d3Force('center', forceCenter(0, 0));    }
  }, [graphData]);
  

  // handle file upload and analyze the paper
  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);
    setGraphData({ nodes: [], links: [] });
    setRelatedPapers([]);
    setSelectedNode(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8000/analyze-paper', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'failed to analyze paper');
      }

      const data = await response.json();
      console.log('server response:', data);

      if (!data || typeof data !== 'object') {
        throw new Error('invalid server response');
      }

      // extract nodes and links from the response
      const graphNodes = data[0]?.nodes || [];
      const graphLinks = data[0]?.links || [];

      // process papers to ensure all required fields are present
      const processedPapers = (data[1] || []).map(paper => ({
        id: paper.id || '',
        title: paper.title || '',
        authors: Array.isArray(paper.authors) ? paper.authors : [],
        summary: paper.summary || '',
        published: paper.published || '',
        topic: paper.topic || ''
      }));

      setGraphData({
        nodes: graphNodes.map(node => ({
          ...node,
          fx: node.group === 'main' ? 0 : undefined,
          fy: node.group === 'main' ? 0 : undefined
        })),
        links: graphLinks
      });
      setRelatedPapers(processedPapers);
      
    } catch (err) {
      console.error('error details:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // handle node click events to show details in the side panel
  const handleNodeClick = (node) => {
    if (node.group === 'main') return; // ignore main node clicks

    setSelectedNode(node);

    if (fgRef.current) {
      // animate to center on the clicked node
      fgRef.current.centerAt(node.x, node.y, 1000); // animate over 1 second
      fgRef.current.zoom(3, 1000); // zoom in over 1 second
    }
  };

  // close the side panel and reset the graph view
  const handleClosePanel = () => {
    setSelectedNode(null);

    if (fgRef.current && initialView.current) {
      // animate back to the initial view
      fgRef.current.centerAt(initialView.current.x, initialView.current.y, 1000); // animate over 1 second
      fgRef.current.zoom(initialView.current.zoom, 1000); // reset zoom over 1 second
    }
  };

  return (
    <div className="space-y-4 relative">
      {/* section for uploading a PDF file */}
      <div className="bg-white p-6 rounded-lg shadow-md">
        <div className="flex items-center justify-center w-full">
          <label 
            htmlFor="dropzone-file" 
            className="flex flex-col items-center justify-center w-full h-64 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            <div className="flex flex-col items-center justify-center pt-5 pb-6">
              <Upload className="w-10 h-10 mb-3 text-gray-400" />
              <p className="mb-2 text-sm text-gray-500">
                <span className="font-semibold">click to upload</span> or drag and drop
              </p>
              <p className="text-xs text-gray-500">pdf files only</p>
            </div>
            <input
              id="dropzone-file"
              type="file"
              className="hidden"
              accept=".pdf"
              onChange={handleFileUpload}
              disabled={loading}
            />
          </label>
        </div>
      </div>

      {/* display an error message if analysis fails */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 p-4 rounded-lg">
          <div className="font-medium">error analyzing paper</div>
          <div className="text-sm mt-1">{error}</div>
          <button 
            onClick={() => window.location.reload()} 
            className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
          >
            try again
          </button>
        </div>
      )}

      {/* show a loading indicator while analyzing the paper */}
      {loading && (
        <div className="text-center p-8 bg-white rounded-lg shadow-md">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto" />
          <p className="mt-4 text-gray-600">analyzing paper...</p>
        </div>
      )}

      {/* display the force-directed graph when data is available */}
      {!loading && !error && graphData.nodes.length > 0 && (
        <div
          className="bg-white rounded-lg shadow-md h-[800px] overflow-hidden"
        >
          <ForceGraph2D
            ref={fgRef}
            graphData={graphData}
            nodeLabel="name"
            nodeRelSize={8}
            // disable manual pan and zoom interactions
            enablePanInteraction={false}
            enableZoomInteraction={false}
            // set limits fo zooming
            minZoom={0.3}
            maxZoom={3}
            enableNodeDrag={false}
            nodeCanvasObject={(node, ctx, globalScale) => {
              if (typeof node.x !== 'number' || typeof node.y !== 'number') return;
            
              const label = node.name;
              const fontSize = 12;
              const baseNodeSize = 2;
              const scaleFactor = 2;
              const nodeSize = baseNodeSize + (node.val * scaleFactor);
            
              // Draw node circle
              ctx.beginPath();
              ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI);
              
              // Different colors for different node types
              ctx.fillStyle = node.group === 'main' ? '#4338ca' :   // Indigo for main
                              node.group === 'topic' ? '#2563eb' :   // Blue for topics
                              '#10b981';                             // Green for subtopics
              ctx.fill();
            
              // Draw outline for subtopics to make them distinct
              if (node.group === 'subtopic') {
                ctx.strokeStyle = '#047857';
                ctx.lineWidth = 2;
                ctx.stroke();
              }
            
              // Draw label if zoomed in enough
              if (globalScale > 0.5) {
                ctx.font = `${fontSize}px Arial`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillStyle = '#1f2937';
                
                // Add slight shadow/outline to text for better readability
                ctx.shadowColor = 'white';
                ctx.shadowBlur = 4;
                ctx.fillText(label, node.x, node.y + nodeSize + 2);
                ctx.shadowBlur = 0;
              }
            }}
            onNodeClick={handleNodeClick}
            linkWidth={2}
            linkColor={() => '#94a3b8'}
            cooldownTicks={100}
            onEngineStop={() => {
              // fix the position of the main node
              const mainNode = graphData.nodes.find((n) => n.group === 'main');
              if (mainNode) {
                mainNode.fx = 0;
                mainNode.fy = 0;
              }

              // set the initial view by zooming to fit the graph
              if (fgRef.current) {
                fgRef.current.zoomToFit(400, 100); // animate over 400ms with 100px padding

                // store the initial view after zooming
                setTimeout(() => {
                  if (fgRef.current) {
                    const { zoom, x, y } = fgRef.current.camera();
                    initialView.current = { zoom, x, y };
                  }
                }, 500); // delay to ensure zoomToFit has completed
              }
            }}
          />
        </div>
      )}

      {/* display the side panel when a node is selected */}
      {selectedNode && (
        <SidePanel
          node={selectedNode}
          papers={relatedPapers}
          onClose={handleClosePanel}
        />
      )}
    </div>
  );
};

export default TopicMap;
