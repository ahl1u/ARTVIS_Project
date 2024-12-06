import './App.css';
import TopicMap from './components/TopicMap';

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto py-8">
        <h1 className="text-3xl font-bold text-center mb-8">Research Paper Topic Map</h1>
        <TopicMap />
      </div>
    </div>
  );
}

export default App;