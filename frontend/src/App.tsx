import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing';
import Editor from './pages/Editor';
import TemplateViewer from './pages/TemplateViewer';
import NotFound from './pages/NotFound';
import Ga4RouteTracker from './components/Ga4RouteTracker';

function App() {
    return (
        <Router basename="/react">
            <Ga4RouteTracker />
            <Routes>
                <Route path="/" element={<Landing />} />
                <Route path="/editor" element={<Editor />} />
                <Route path="/template-viewer/:templateName" element={<TemplateViewer />} />
                <Route path="/template-download/:templateName" element={<TemplateViewer />} />
                <Route path="*" element={<NotFound />} />
            </Routes>
        </Router>
    );
}

export default App;
