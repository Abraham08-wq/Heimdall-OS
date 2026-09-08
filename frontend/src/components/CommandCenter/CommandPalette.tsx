import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export interface Command {
  id: string;
  label: string;
  description: string;
  action: () => void;
  category: 'battlefield' | 'intelligence' | 'offensive' | 'tools';
  hotkey?: string;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  commands: Command[];
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  commands,
}) => {
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredCommands = commands.filter(
    (cmd) =>
      cmd.label.toLowerCase().includes(search.toLowerCase()) ||
      cmd.description.toLowerCase().includes(search.toLowerCase())
  );

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
      setSearch('');
      setSelectedIndex(0);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((prev) =>
            prev < filteredCommands.length - 1 ? prev + 1 : prev
          );
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((prev) => (prev > 0 ? prev - 1 : 0));
          break;
        case 'Enter':
          e.preventDefault();
          if (filteredCommands[selectedIndex]) {
            filteredCommands[selectedIndex].action();
            onClose();
          }
          break;
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, filteredCommands, selectedIndex, onClose]);

  const groupedCommands = filteredCommands.reduce(
    (acc, cmd) => {
      if (!acc[cmd.category]) {
        acc[cmd.category] = [];
      }
      acc[cmd.category].push(cmd);
      return acc;
    },
    {} as Record<string, Command[]>
  );

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Enhanced Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
          />

          {/* Enhanced Command Palette */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: -30 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: -30 }}
            transition={{ duration: 0.25, type: 'spring', damping: 20 }}
            className="fixed left-1/2 top-1/4 z-50 w-full max-w-3xl -translate-x-1/2 rounded-2xl bg-white/8 backdrop-blur-xl border border-white/20 shadow-2xl overflow-hidden group"
          >
            {/* Enhanced Search Input */}
            <div className="border-b border-white/10 p-5 bg-gradient-to-r from-blue-500/10 via-transparent to-cyan-500/10">
              <div className="flex items-center gap-3 mb-3">
                <span className="text-blue-400 font-bold">⌘</span>
                <span className="text-white/60 font-mono text-sm">COMMAND PALETTE</span>
              </div>
              <input
                ref={inputRef}
                type="text"
                placeholder="Search commands... (Esc to close)"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setSelectedIndex(0);
                }}
                className="w-full bg-white/5 border border-white/10 focus:border-blue-400/50 rounded-lg px-4 py-3 text-white placeholder-white/40 text-lg outline-none font-mono transition-colors focus:bg-white/10"
              />
            </div>

            {/* Enhanced Commands List */}
            <div className="max-h-[28rem] overflow-y-auto custom-scrollbar">
              {Object.entries(groupedCommands).length === 0 ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="p-12 text-center"
                >
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-white/5 border border-white/10 mb-4">
                    <span className="text-3xl">🔍</span>
                  </div>
                  <p className="text-white/50 font-mono text-sm">No commands found</p>
                </motion.div>
              ) : (
                Object.entries(groupedCommands).map(([category, cmds], catIdx) => (
                  <motion.div
                    key={category}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: catIdx * 0.05 }}
                  >
                    {/* Enhanced Category Header */}
                    <div className="px-5 pt-4 pb-2">
                      <span className="text-xs font-mono font-bold text-white/40 uppercase tracking-widest">
                        {category === 'battlefield' && '🗺️ Battlefield'}
                        {category === 'intelligence' && '📊 Intelligence'}
                        {category === 'offensive' && '⚔️ Offensive'}
                        {category === 'tools' && '🛠️ Tools'}
                      </span>
                    </div>

                    {/* Enhanced Commands in Category */}
                    {cmds.map((cmd, cmdIdx) => {
                      const isSelected = selectedIndex === filteredCommands.indexOf(cmd);

                      return (
                        <motion.button
                          key={cmd.id}
                          onClick={() => {
                            cmd.action();
                            onClose();
                          }}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: catIdx * 0.05 + cmdIdx * 0.02 }}
                          whileHover={{ x: 4 }}
                          whileTap={{ scale: 0.98 }}
                          className={`w-full px-5 py-4 text-left transition-all border-l-2 ${
                            isSelected
                              ? 'bg-gradient-to-r from-blue-500/20 to-cyan-500/10 border-l-blue-400 shadow-lg shadow-blue-500/20'
                              : 'border-l-transparent hover:bg-white/5 hover:border-l-white/20'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-4">
                            <div className="flex-1 min-w-0">
                              <motion.div
                                className={`text-sm font-mono font-bold transition-colors ${
                                  isSelected ? 'text-blue-300' : 'text-white'
                                }`}
                              >
                                {cmd.label}
                              </motion.div>
                              <div className={`text-xs font-mono mt-1 transition-colors ${
                                isSelected ? 'text-blue-200/70' : 'text-white/50'
                              }`}>
                                {cmd.description}
                              </div>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              {cmd.hotkey && (
                                <span className={`text-xs font-mono font-bold px-2 py-1 rounded-lg transition-colors ${
                                  isSelected 
                                    ? 'bg-blue-400/30 text-blue-200' 
                                    : 'bg-white/10 text-white/50 group-hover:bg-white/20'
                                }`}>
                                  {cmd.hotkey}
                                </span>
                              )}
                              {isSelected && (
                                <motion.div
                                  animate={{ x: [0, 3, 0] }}
                                  transition={{ duration: 1, repeat: Infinity }}
                                  className="text-blue-400 text-lg"
                                >
                                  →
                                </motion.div>
                              )}
                            </div>
                          </div>
                        </motion.button>
                      );
                    })}
                  </motion.div>
                ))
              )}
            </div>

            {/* Enhanced Footer */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="border-t border-white/10 px-5 py-3 bg-gradient-to-r from-white/5 to-transparent flex items-center justify-between text-xs font-mono text-white/40"
            >
              <span>{filteredCommands.length} command{filteredCommands.length !== 1 ? 's' : ''} available</span>
              <span className="text-white/30">
                ↑ ↓ to select • ⏎ to execute • ESC to close
              </span>
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
