/**
 * Persistent ask bar -> POST /api/search. Documents only (CLAUDE.md rule 8).
 * No intent routing. Low-similarity results get the fixed redirect string
 * from spec 7.1 rather than a wrong answer.
 */
import { useState } from 'react';
import { searchSOPs, explainSOPs } from '../api/client';
import type { ExplainResponse, SopResult } from '../api/types';
import { Search, ChevronDown } from 'lucide-react';

export function AskBar() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SopResult[]>([]);
  const [fallback, setFallback] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<ExplainResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [expandedResult, setExpandedResult] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim().length < 3) return;

    setLoading(true);
    setExplanation(null);
    setExpandedResult(null);

    try {
      const data = await searchSOPs(query.trim());
      setResults(data.results);
      setFallback(data.fallbackMessage);
      setShowResults(true);
    } catch (error) {
      console.error('Search failed:', error);
      setResults([]);
      setFallback('Search is unavailable right now.');
      setShowResults(true);
    } finally {
      setLoading(false);
    }
  };

  const handleExplain = async (sopIds: string[]) => {
    setLoading(true);
    try {
      setExplanation(await explainSOPs(query.trim(), sopIds));
    } catch (error) {
      console.error('Explanation failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-blue-50 border-b-2 border-blue-200 p-6 sticky top-0 z-10">
      {/* Search Bar */}
      <form onSubmit={handleSearch} className="max-w-2xl">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-3 text-gray-400 w-5 h-5" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about SOPs, procedures, troubleshooting..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </form>

      {/* Results */}
      {showResults && results.length > 0 && (
        <div className="mt-6 space-y-3 max-w-2xl">
          {results.map((result) => (
            <div key={result.id} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              {/* Result Header */}
              <button
                onClick={() => setExpandedResult(expandedResult === result.id ? null : result.id)}
                className="w-full p-4 text-left hover:bg-gray-50 flex justify-between items-start"
              >
                <div>
                  <h3 className="font-semibold text-gray-900">{result.title}</h3>
                  <p className="text-sm text-gray-500">{result.section}</p>
                </div>
                <ChevronDown
                  className={`w-5 h-5 text-gray-400 transform transition ${expandedResult === result.id ? 'rotate-180' : ''
                    }`}
                />
              </button>

              {/* Expanded Content */}
              {expandedResult === result.id && (
                <div className="border-t border-gray-200 bg-gray-50 p-4">
                  <p className="text-sm text-gray-700 mb-4">{result.content}</p>
                  <button
                    onClick={() => handleExplain([result.id])}
                    disabled={loading}
                    className="text-sm px-3 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50"
                  >
                    {loading ? 'Explaining...' : 'Explain This Step-by-Step'}
                  </button>
                </div>
              )}
            </div>
          ))}

          {/* AI Explanation. Generated fields may be null if the model failed. */}
          {explanation && (
            <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4">
              <h4 className="font-semibold text-green-900 mb-2">AI Explanation</h4>
              {explanation.explanation ? (
                <>
                  <p className="text-sm text-gray-700 mb-3">{explanation.explanation}</p>
                  {explanation.steps && (
                    <ol className="text-sm text-gray-700 mb-3 space-y-1 list-decimal list-inside">
                      {explanation.steps.map((step, i) => (
                        <li key={i}>
                          <span className="font-medium">{step.action}</span>
                          <span className="text-gray-500"> — {step.why}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                  {explanation.commonMistake && (
                    <p className="text-sm text-amber-800 mb-3">
                      Common mistake: {explanation.commonMistake}
                    </p>
                  )}
                  {explanation.estimatedMinutes !== null && (
                    <p className="text-xs text-gray-500">
                      Estimated time: {explanation.estimatedMinutes} min
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-gray-600 mb-3">
                  Explanation unavailable. The SOP text above is unchanged.
                </p>
              )}
              <p className="text-xs text-gray-500 mt-2">
                Sources: {explanation.sources.join(', ')}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Spec 7.1 redirect, or an empty corpus */}
      {showResults && results.length === 0 && !loading && (
        <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-sm max-w-2xl">
          {fallback ?? 'No SOPs found. Try different keywords.'}
        </div>
      )}
    </div>
  );
}