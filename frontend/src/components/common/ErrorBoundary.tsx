import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught React UI error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 max-w-xl mx-auto my-12 glass-panel rounded-2xl border border-rose-500/30 text-center space-y-4">
          <AlertCircle className="w-10 h-10 text-rose-400 mx-auto animate-pulse" />
          <h2 className="text-lg font-bold text-white">Workspace Render Error</h2>
          <p className="text-xs text-slate-300 font-mono bg-slate-950 p-3 rounded-xl border border-slate-800">
            {this.state.error?.message || 'An unexpected UI rendering error occurred.'}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white text-xs font-bold rounded-xl shadow transition-all flex items-center justify-center gap-2 mx-auto"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Reload Workspace</span>
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
