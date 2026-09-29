import React, { useState, useEffect } from 'react';
import { ShieldCheck, Plus, Link as LinkIcon, Loader2, Search } from 'lucide-react';
import { apiService } from '../../services/api';
import { InternalControl } from '../../types';

export const ControlsLibrary: React.FC = () => {
  const [controls, setControls] = useState<InternalControl[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showMapModal, setShowMapModal] = useState<string | null>(null);

  // Forms
  const [newControl, setNewControl] = useState({
    control_code: '',
    name: '',
    description: '',
    category: 'TECHNICAL',
    owner_department: 'IT Security',
    status: 'DRAFT',
  });
  const [mapForm, setMapForm] = useState({ obligationId: '', rationale: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadControls();
  }, []);

  const loadControls = async () => {
    try {
      setLoading(true);
      const data = await apiService.getControls();
      setControls(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load controls');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateControl = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      await apiService.createControl(newControl);
      setShowCreateModal(false);
      setNewControl({
        control_code: '',
        name: '',
        description: '',
        category: 'TECHNICAL',
        owner_department: 'IT Security',
        status: 'DRAFT',
      });
      await loadControls();
    } catch (err: any) {
      alert(err.message || 'Failed to create control');
    } finally {
      setSaving(false);
    }
  };

  const handleMapControl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showMapModal) return;
    try {
      setSaving(true);
      await apiService.mapControlToObligation(showMapModal, mapForm.obligationId, mapForm.rationale);
      setShowMapModal(null);
      setMapForm({ obligationId: '', rationale: '' });
      alert("Successfully mapped control to obligation!");
    } catch (err: any) {
      alert(err.message || 'Failed to map control');
    } finally {
      setSaving(false);
    }
  };

  if (loading && controls.length === 0) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck className="w-5 h-5 text-brand-400" />
            <h1 className="text-lg font-bold text-white tracking-tight">Controls Library</h1>
          </div>
          <p className="text-xs text-slate-400">
            Manage your internal controls and map them to regulatory obligations.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Create Control
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Grid */}
      {controls.length === 0 && !loading && !error ? (
        <div className="glass-panel p-12 rounded-2xl flex flex-col items-center justify-center text-center">
          <ShieldCheck className="w-12 h-12 text-slate-600 mb-4" />
          <h3 className="text-sm font-bold text-white mb-2">No Controls Found</h3>
          <p className="text-xs text-slate-400 mb-6 max-w-sm">
            You haven't defined any internal controls yet. Create one to start mapping against regulatory obligations.
          </p>
          <button onClick={() => setShowCreateModal(true)} className="btn-primary">
            Create First Control
          </button>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {controls.map((control) => (
            <div key={control.id} className="glass-panel p-4 rounded-2xl flex flex-col">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-1 bg-slate-800 text-slate-300 rounded text-[10px] font-mono border border-slate-700">
                    {control.control_code}
                  </span>
                  <span className={`px-2 py-1 rounded text-[10px] font-bold ${
                    control.status === 'EFFECTIVE' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/20' :
                    control.status === 'INEFFECTIVE' ? 'bg-red-500/20 text-red-400 border border-red-500/20' :
                    control.status === 'CONTROL_GAP' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/20' :
                    'bg-slate-800 text-slate-400 border border-slate-700'
                  }`}>
                    {control.status}
                  </span>
                </div>
              </div>
              <h3 className="text-sm font-bold text-white mb-1 line-clamp-1">{control.name}</h3>
              <p className="text-xs text-slate-400 mb-4 line-clamp-2 flex-1">{control.description}</p>
              
              <div className="pt-4 mt-auto border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-500">
                <span>{control.owner_department}</span>
                <button
                  onClick={() => setShowMapModal(control.id)}
                  className="flex items-center gap-1 hover:text-brand-400 transition-colors"
                >
                  <LinkIcon className="w-3 h-3" />
                  Map Obligation
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 w-full max-w-md">
            <h2 className="text-base font-bold text-white mb-4">Create Internal Control</h2>
            <form onSubmit={handleCreateControl} className="space-y-4 text-xs">
              <div>
                <label className="form-label">Control Code</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. AC-1"
                  className="form-input"
                  value={newControl.control_code}
                  onChange={(e) => setNewControl({...newControl, control_code: e.target.value})}
                />
              </div>
              <div>
                <label className="form-label">Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Access Control Policy"
                  className="form-input"
                  value={newControl.name}
                  onChange={(e) => setNewControl({...newControl, name: e.target.value})}
                />
              </div>
              <div>
                <label className="form-label">Description</label>
                <textarea
                  required
                  rows={3}
                  className="form-input"
                  value={newControl.description}
                  onChange={(e) => setNewControl({...newControl, description: e.target.value})}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="form-label">Category</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    value={newControl.category}
                    onChange={(e) => setNewControl({...newControl, category: e.target.value})}
                  />
                </div>
                <div>
                  <label className="form-label">Owner Dept</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    value={newControl.owner_department}
                    onChange={(e) => setNewControl({...newControl, owner_department: e.target.value})}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-slate-800">
                <button type="button" onClick={() => setShowCreateModal(false)} className="btn-secondary">Cancel</button>
                <button type="submit" disabled={saving} className="btn-primary">
                  {saving ? 'Creating...' : 'Create Control'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Map Modal */}
      {showMapModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 w-full max-w-md">
            <h2 className="text-base font-bold text-white mb-4">Map to Regulatory Obligation</h2>
            <form onSubmit={handleMapControl} className="space-y-4 text-xs">
              <div>
                <label className="form-label">Obligation ID</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. obl-1234..."
                  className="form-input"
                  value={mapForm.obligationId}
                  onChange={(e) => setMapForm({...mapForm, obligationId: e.target.value})}
                />
                <p className="text-[10px] text-slate-500 mt-1">Provide the exact Obligation ID from the Repository.</p>
              </div>
              <div>
                <label className="form-label">Rationale</label>
                <textarea
                  rows={2}
                  className="form-input"
                  placeholder="Why does this control satisfy the obligation?"
                  value={mapForm.rationale}
                  onChange={(e) => setMapForm({...mapForm, rationale: e.target.value})}
                />
              </div>
              <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-slate-800">
                <button type="button" onClick={() => setShowMapModal(null)} className="btn-secondary">Cancel</button>
                <button type="submit" disabled={saving} className="btn-primary">
                  {saving ? 'Mapping...' : 'Map Obligation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
