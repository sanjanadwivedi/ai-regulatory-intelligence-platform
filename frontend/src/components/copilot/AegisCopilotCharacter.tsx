import React from 'react';
import { Sparkles, Bot, MessageSquare } from 'lucide-react';

interface AegisCopilotCharacterProps {
  size?: 'sm' | 'md' | 'lg';
  isThinking?: boolean;
  onClick?: () => void;
  showMessageBubble?: boolean;
  message?: string;
}

export const AegisCopilotCharacter: React.FC<AegisCopilotCharacterProps> = ({
  size = 'md',
  isThinking = false,
  onClick,
  showMessageBubble = false,
  message = 'Ask Aegis AI about any regulation...',
}) => {
  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-16 h-16',
  };

  const iconSizes = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-8 h-8',
  };

  return (
    <div className="relative inline-flex items-center group select-none cursor-pointer" onClick={onClick}>
      {/* Outer Holographic Glow / Aura */}
      <div
        className={`absolute inset-0 rounded-2xl bg-gradient-to-tr from-brand-500 via-cyan-400 to-indigo-500 opacity-60 blur-md group-hover:opacity-100 transition-opacity ${
          isThinking ? 'animate-spin' : 'animate-pulse'
        }`}
      />

      {/* Main Bot Character Body */}
      <button
        type="button"
        className={`relative ${sizeClasses[size]} rounded-2xl bg-slate-950 border border-brand-400/50 flex items-center justify-center shadow-2xl transition-all duration-300 transform group-hover:scale-110 group-hover:border-cyan-300 focus:outline-none`}
      >
        {/* Animated Cyber Core Grid */}
        <div className="absolute inset-0 rounded-2xl bg-gradient-to-b from-brand-500/20 to-transparent pointer-events-none" />

        {/* Character Core */}
        <div className="relative flex items-center justify-center">
          <Bot className={`${iconSizes[size]} text-cyan-300 drop-shadow-[0_0_8px_rgba(34,211,238,0.8)] transition-transform group-hover:rotate-6`} />

          {/* Sparkle Ear Antenna */}
          <Sparkles className="absolute -top-1 -right-1 w-3 h-3 text-amber-300 animate-bounce" />
        </div>

        {/* Status Indicator Pip */}
        <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-400 border-2 border-slate-950 rounded-full shadow-[0_0_8px_#34d399]" />
      </button>

      {/* Optional Speech Bubble */}
      {showMessageBubble && (
        <div className="hidden sm:flex items-center gap-2 ml-3 px-3.5 py-1.5 rounded-2xl bg-slate-900/90 border border-brand-500/30 text-xs text-slate-200 shadow-xl backdrop-blur-md pointer-events-none">
          <MessageSquare className="w-3.5 h-3.5 text-brand-400" />
          <span className="font-semibold text-slate-300">{message}</span>
        </div>
      )}
    </div>
  );
};
