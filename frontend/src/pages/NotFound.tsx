import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export default function NotFound() {
  const location = useLocation();
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-lg p-8 max-w-lg w-full">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Page not found</h1>
        <p className="text-gray-700 mb-4">
          No route matched <span className="font-mono text-sm">{location.pathname}</span>.
        </p>
        <div className="flex items-center gap-2">
          <Link
            to="/"
            className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
          >
            Go to Home
          </Link>
          <a
            href="/results"
            className="px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-800 hover:bg-gray-50 transition-colors"
          >
            Go to Results
          </a>
        </div>
        <p className="text-xs text-gray-500 mt-6">
          Tip: Template viewer URLs look like <span className="font-mono">/react/template-viewer/professional</span>.
        </p>
      </div>
    </div>
  );
}


