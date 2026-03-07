import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { ensureGa4Loaded, trackGa4PageView } from '../utils/ga4';

export default function Ga4RouteTracker() {
    const location = useLocation();

    useEffect(() => {
        ensureGa4Loaded();
    }, []);

    useEffect(() => {
        // Use the real browser URL so basename (/react) is included.
        const pagePath = `${window.location.pathname}${window.location.search || ''}`;
        trackGa4PageView(pagePath);
    }, [location.pathname, location.search]);

    return null;
}
