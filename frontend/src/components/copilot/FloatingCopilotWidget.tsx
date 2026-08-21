import React, { useState } from 'react';
import { AegisCopilotCharacter } from './AegisCopilotCharacter';
import { MessageSquare, Sparkles, X, Send, Maximize2, Minimize2, ExternalLink, ShieldCheck, User, Bot } from 'lucide-react';
import { ServiceAPI } from '../../services/api';
import { GroundedCitation } from '../../types';

interface FloatingCopilotWidgetProps {
  onOpenFullCopilot: (query?: string) => void;
}

interface ChatMessage {
  sender: 'user' | 'bot';
  text: string;
  citations?: GroundedCitation[];
  confidence?: number;
}

export const FloatingCopilotWidget: React.FC<FloatingCopilotWidgetProps> = ({
  onOpenFullCopilot,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const userQ = query;
    setQuery('');
    setMessages((prev) => [...prev, { sender: 'user', text: userQ }]);
    setLoading(true);

    try {
      const res = await ServiceAPI.queryCopilot(userQ);
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: res.answer,
          citations: res.grounded_citations,
          confidence: res.confidence_score,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: 'Connected to Aegis Statutory Knowledge Base. Please review your active regulations or try rephrasing.',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end space-y-3">
      {/* Interactive Chat Popup / Drawer */}
      {isOpen && (
        <div
          className={`glass-panel rounded-3xl border border-brand-500/40 bg-slate-950/95 backdrop-blur-2xl shadow-2xl flex flex-col transition-all duration-300 animate-in fade-in slide-in-from-bottom-4 ${
            isMaximized
              ? 'fixed inset-4 sm:inset-10 z-50 p-6 max-w-5xl mx-auto h-[calc(100vh-5rem)]'
              : 'w-80 sm:w-96 p-4 space-y-3 max-h-[550px]'
          }`}
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
            <div className="flex items-center space-x-3">
              <AegisCopilotCharacter size={isMaximized ? 'md' : 'sm'} isThinking={loading} />
              <div>
                <h4 className="text-xs sm:text-sm font-bold text-white flex items-center gap-1.5">
                  Aegis AI Copilot
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                </h4>
                <p className="text-[10px] text-slate-400">Grounded Regulatory RAG Assistant</p>
              </div>
            </div>

            <div className="flex items-center space-x-1.5">
              {/* Navigate to Full Copilot Page */}
              <button
                onClick={() => {
                  setIsOpen(false);
                  onOpenFullCopilot(query || (messages.length > 0 ? messages[messages.length - 1].text : ''));
                }}
                title="Open Dedicated Full Workspace"
                className="text-slate-400 hover:text-white p-1.5 rounded-xl hover:bg-slate-800/80 transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
              </button>

              {/* Maximize / Restore Button */}
              <button
                onClick={() => setIsMaximized(!isMaximized)}
                title={isMaximized ? 'Restore View' : 'Maximize Window'}
                className="text-slate-400 hover:text-white p-1.5 rounded-xl hover:bg-slate-800/80 transition-colors"
              >
                {isMaximized ? <Minimize2 className="w-4 h-4 text-cyan-300" /> : <Maximize2 className="w-4 h-4" />}
              </button>

              {/* Close Button */}
              <button
                onClick={() => {
                  setIsOpen(false);
                  setIsMaximized(false);
                }}
                title="Close Assistant"
                className="text-slate-400 hover:text-white p-1.5 rounded-xl hover:bg-slate-800/80 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Messages Feed Area */}
          <div
            className={`flex-1 overflow-y-auto space-y-3 p-3 rounded-2xl bg-slate-900/80 border border-slate-800/80 text-xs text-slate-200 leading-relaxed font-sans ${
              isMaximized ? 'my-4 p-5' : 'min-h-[140px] max-h-64'
            }`}
          >
            {messages.length === 0 && !loading && (
              <div className="text-center py-6 space-y-2">
                <p className="text-slate-400 text-xs font-medium">
                  👋 Hi! I am Aegis AI. Ask me any question regarding your compliance circulars, deadlines, or controls!
                </p>
                <div className="flex flex-wrap gap-1.5 justify-center pt-2">
                  {[
                    'What are high-risk KYC timelines?',
                    'Explain CERT-In 6-hour reporting',
                    'Summarize HIPAA EHR audit controls',
                  ].map((preset, idx) => (
                    <button
                      key={idx}
                      onClick={() => setQuery(preset)}
                      className="text-[10px] bg-slate-950/80 hover:bg-brand-500/20 text-slate-300 hover:text-brand-200 px-2.5 py-1 rounded-xl border border-slate-800 transition-colors"
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex items-start space-x-2.5 ${m.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}
              >
                <div className="shrink-0 pt-0.5">
                  {m.sender === 'user' ? (
                    <div className="w-6 h-6 rounded-lg bg-brand-600 flex items-center justify-center text-[10px] font-bold text-white shadow-md">
                      <User className="w-3.5 h-3.5" />
                    </div>
                  ) : (
                    <AegisCopilotCharacter size="sm" isThinking={false} />
                  )}
                </div>

                <div
                  className={`p-3 rounded-2xl text-xs space-y-2 ${
                    m.sender === 'user'
                      ? 'bg-brand-600 text-white rounded-tr-none max-w-[80%]'
                      : 'bg-slate-950/90 border border-slate-800 text-slate-200 rounded-tl-none max-w-[90%]'
                  }`}
                >
                  <p className="whitespace-pre-line leading-relaxed">{m.text}</p>

                  {/* Citations Preview in Maximized or Normal Mode */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="pt-2 border-t border-slate-800 space-y-1.5 text-[11px]">
                      <span className="font-bold text-cyan-400 flex items-center gap-1 text-[10px] uppercase">
                        <ShieldCheck className="w-3 h-3" /> Grounded Citations ({m.citations.length})
                      </span>
                      {m.citations.map((c, cIdx) => (
                        <div key={cIdx} className="p-2 rounded-xl bg-slate-900 border border-slate-800/80 text-[10px] text-slate-300">
                          <span className="font-bold text-white block">{c.authority || c.regulation_title}</span>
                          <span className="text-slate-400 line-clamp-2 mt-0.5">{c.section_text || c.highlighted_sentence}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex items-center space-x-2.5 text-slate-400 text-xs py-2">
                <AegisCopilotCharacter size="sm" isThinking={true} />
                <div className="flex items-center space-x-1.5 animate-pulse text-cyan-300">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Synthesizing grounded citations...</span>
                </div>
              </div>
            )}
          </div>

          {/* Input Form Bar */}
          <form onSubmit={handleAsk} className="flex items-center space-x-2 shrink-0">
            <input
              type="text"
              placeholder="Ask Aegis AI about any regulation or control..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-800 rounded-2xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="p-2.5 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white rounded-2xl shadow-lg transition-all"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}

      {/* Floating Animated Character Orb Button */}
      <div className="flex items-center space-x-2">
        {!isOpen && (
          <div
            onClick={() => setIsOpen(true)}
            className="hidden sm:flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-slate-900/90 border border-brand-500/30 text-[11px] font-semibold text-slate-200 shadow-xl cursor-pointer hover:border-brand-400 transition-all backdrop-blur-md"
          >
            <Sparkles className="w-3 h-3 text-brand-400" />
            <span>Ask Aegis AI</span>
          </div>
        )}
        <AegisCopilotCharacter
          size="md"
          isThinking={loading}
          onClick={() => {
            setIsOpen(!isOpen);
            if (isOpen) setIsMaximized(false);
          }}
        />
      </div>
    </div>
  );
};

