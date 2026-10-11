import React, { useState } from 'react';
import {
  Search,
  Filter,
  LayoutGrid,
  Columns3,
  AlertOctagon,
  Stethoscope,
  Pill,
  Utensils,
  Wrench,
  ClipboardList,
  Layers,
  Inbox
} from 'lucide-react';
import { Ticket, TicketStatus, UrgencyTier } from '../types';
import { TicketCard } from './TicketCard';

interface TicketBoardProps {
  tickets: Ticket[];
  onSelectTicket: (ticket: Ticket) => void;
  onUpdateStatus: (ticketId: number, status: TicketStatus) => void;
}

const DEPARTMENTS = [
  'All',
  'Rapid Response & Critical Nursing',
  'Nursing & Clinical Care',
  'Pharmacy & Therapeutics',
  'Dietary & Clinical Nutrition',
  'Facilities & Environmental Services',
  'Administration & Discharge Coordination'
];

export const TicketBoard: React.FC<TicketBoardProps> = ({
  tickets,
  onSelectTicket,
  onUpdateStatus
}) => {
  const [selectedDept, setSelectedDept] = useState<string>('All');
  const [selectedUrgency, setSelectedUrgency] = useState<string>('All');
  const [selectedStatus, setSelectedStatus] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [viewMode, setViewMode] = useState<'grid' | 'kanban'>('grid');

  // Filter tickets
  const filteredTickets = tickets.filter((t) => {
    if (selectedDept !== 'All' && !t.department.toLowerCase().includes(selectedDept.toLowerCase())) {
      return false;
    }
    if (selectedUrgency !== 'All' && t.urgency !== selectedUrgency) {
      return false;
    }
    if (selectedStatus !== 'All' && t.status !== selectedStatus) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const match =
        t.title.toLowerCase().includes(q) ||
        t.patient_name.toLowerCase().includes(q) ||
        t.room_number.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q) ||
        t.assigned_to.toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  // Calculate department counters
  const getDeptCount = (deptName: string) => {
    if (deptName === 'All') return tickets.length;
    return tickets.filter((t) => t.department.toLowerCase().includes(deptName.toLowerCase())).length;
  };

  const getShortDeptLabel = (deptName: string) => {
    if (deptName === 'All') return 'All Tasks';
    if (deptName.includes('Rapid Response')) return 'Rapid Response';
    if (deptName.includes('Nursing')) return 'Nursing';
    if (deptName.includes('Pharmacy')) return 'Pharmacy';
    if (deptName.includes('Dietary')) return 'Dietary';
    if (deptName.includes('Facilities')) return 'Facilities';
    return 'Admin & Discharge';
  };

  const getDeptIcon = (deptName: string) => {
    if (deptName.includes('Rapid Response')) return AlertOctagon;
    if (deptName.includes('Nursing')) return Stethoscope;
    if (deptName.includes('Pharmacy')) return Pill;
    if (deptName.includes('Dietary')) return Utensils;
    if (deptName.includes('Facilities')) return Wrench;
    if (deptName.includes('Admin')) return ClipboardList;
    return Layers;
  };

  return (
    <div className="space-y-4">
      
      {/* Top Filter & Search Bar */}
      <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-3">
        
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          {/* Search Bar */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              id="ticket-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by patient, room 314, symptoms, IV alarm, meds..."
              className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
            />
          </div>

          {/* Urgency & Status Dropdowns + View Mode Toggle */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Urgency Filter */}
            <select
              value={selectedUrgency}
              onChange={(e) => setSelectedUrgency(e.target.value)}
              id="urgency-filter-select"
              aria-label="Filter by urgency"
              className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-sky-500 cursor-pointer"
            >
              <option value="All">All Urgencies</option>
              <option value="STAT_EMERGENCY">🚨 STAT Emergency</option>
              <option value="URGENT">⚠️ Urgent (15m SLA)</option>
              <option value="ROUTINE">Routine</option>
              <option value="INQUIRY">Inquiry</option>
            </select>

            {/* Status Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              id="status-filter-select"
              aria-label="Filter by task status"
              className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-sky-500 cursor-pointer"
            >
              <option value="All">All Statuses</option>
              <option value="PENDING">Pending Triage</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="DISPATCHED">Dispatched</option>
              <option value="RESOLVED">Resolved</option>
            </select>

            {/* Layout View Toggle */}
            <div className="flex items-center p-1 rounded-xl bg-slate-950 border border-slate-800">
              <button
                onClick={() => setViewMode('grid')}
                id="view-grid-btn"
                className={`p-1.5 rounded-lg text-xs transition-colors ${
                  viewMode === 'grid' ? 'bg-sky-500/20 text-sky-400 font-bold' : 'text-slate-400 hover:text-white'
                }`}
                title="Grid View"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('kanban')}
                id="view-kanban-btn"
                className={`p-1.5 rounded-lg text-xs transition-colors ${
                  viewMode === 'kanban' ? 'bg-sky-500/20 text-sky-400 font-bold' : 'text-slate-400 hover:text-white'
                }`}
                title="Kanban Board View"
              >
                <Columns3 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Department Filter Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-1 no-scrollbar">
          {DEPARTMENTS.map((dept) => {
            const isSelected = selectedDept === dept;
            const count = getDeptCount(dept);
            const DeptIcon = getDeptIcon(dept);

            return (
              <button
                key={dept}
                onClick={() => setSelectedDept(dept)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 shrink-0 ${
                  isSelected
                    ? 'bg-sky-500 text-white shadow-md shadow-sky-500/30'
                    : 'bg-slate-950/70 text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 border border-slate-800'
                }`}
              >
                <DeptIcon className="w-3.5 h-3.5" />
                <span>{getShortDeptLabel(dept)}</span>
                <span
                  className={`ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                    isSelected ? 'bg-white/20 text-white' : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

      </div>

      {/* Main Tickets Display */}
      {filteredTickets.length === 0 ? (
        <div className="p-12 text-center rounded-2xl bg-slate-900/40 border border-slate-800 flex flex-col items-center justify-center space-y-3">
          <div className="p-3 rounded-full bg-slate-800/60 text-slate-500">
            <Inbox className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-300">No Tickets Match Filters</h3>
            <p className="text-xs text-slate-500 max-w-sm mt-1">
              Try adjusting your department filter, clearing search, or process a new phone call using the button above.
            </p>
          </div>
        </div>
      ) : viewMode === 'grid' ? (
        /* Grid View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTickets.map((ticket) => (
            <TicketCard
              key={ticket.id}
              ticket={ticket}
              onSelect={onSelectTicket}
              onUpdateStatus={onUpdateStatus}
            />
          ))}
        </div>
      ) : (
        /* Kanban Columns View */
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-start">
          {(['PENDING', 'IN_PROGRESS', 'DISPATCHED', 'RESOLVED'] as TicketStatus[]).map((colStatus) => {
            const colTickets = filteredTickets.filter((t) => t.status === colStatus);
            const colTitles: Record<TicketStatus, { title: string; color: string }> = {
              PENDING: { title: 'Pending Triage', color: 'text-amber-400 border-amber-500/30' },
              IN_PROGRESS: { title: 'In Progress', color: 'text-sky-400 border-sky-500/30' },
              DISPATCHED: { title: 'Dispatched', color: 'text-purple-400 border-purple-500/30' },
              RESOLVED: { title: 'Resolved', color: 'text-emerald-400 border-emerald-500/30' }
            };

            return (
              <div
                key={colStatus}
                className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-3 flex flex-col space-y-3"
              >
                <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                  <h4 className={`text-xs font-bold ${colTitles[colStatus].color}`}>
                    {colTitles[colStatus].title}
                  </h4>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-300">
                    {colTickets.length}
                  </span>
                </div>

                <div className="space-y-3">
                  {colTickets.length === 0 ? (
                    <div className="py-8 text-center text-[11px] text-slate-600 italic">
                      No tasks in this lane
                    </div>
                  ) : (
                    colTickets.map((ticket) => (
                      <TicketCard
                        key={ticket.id}
                        ticket={ticket}
                        onSelect={onSelectTicket}
                        onUpdateStatus={onUpdateStatus}
                      />
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
};
