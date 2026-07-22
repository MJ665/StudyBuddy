'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { useKTNavStore } from '@/stores/ktNavStore';
import ApiService from '@/services/ApiService';
import { Loader2, ZoomIn, ZoomOut, Maximize2, RefreshCw, Filter, Info, Network, Database, Layers, AlertCircle } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { motion, AnimatePresence } from 'motion/react';

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: 'organization' | 'company' | 'project' | 'sprint' | 'document' | 'episode' | 'entity';
  depth: number;
  metadata?: Record<string, any>;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  type: string;
}

const NODE_CONFIG: Record<string, { radius: number; color: string; strokeColor: string; label: string }> = {
  organization: { radius: 40, color: '#f59e0b', strokeColor: '#d97706', label: 'ORG' },
  company:      { radius: 30, color: '#6366f1', strokeColor: '#4f46e5', label: 'CO' },
  project:      { radius: 22, color: '#06b6d4', strokeColor: '#0891b2', label: 'PRJ' },
  sprint:       { radius: 16, color: '#8b5cf6', strokeColor: '#7c3aed', label: 'SPR' },
  document:     { radius: 12, color: '#10b981', strokeColor: '#059669', label: 'DOC' },
  episode:      { radius: 8,  color: '#ec4899', strokeColor: '#db2777', label: 'EP' },
  entity:       { radius: 5,  color: '#f59e0b', strokeColor: '#d97706', label: 'ENT' },
};

export default function KnowledgeExplorer({ 
  projectId, 
  accessKey 
}: { projectId?: string; accessKey?: string }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphLink> | null>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [nodeCount, setNodeCount] = useState(0);
  const [filterTypes, setFilterTypes] = useState<Set<string>>(
    new Set(['organization', 'company', 'project', 'sprint', 'document', 'episode', 'entity'])
  );
  
  const { selectedCompany } = useKTNavStore();


  const hopToNode = async () => {
    if (!selectedNode) return;
    setLoading(true);
    try {
      const data = await ApiService.getKTGraphNeighborhoodData(selectedNode.id as string, accessKey);
      const nodes: GraphNode[] = (data.nodes || []).map((n: any) => ({
        ...n,
        depth: ['organization', 'company', 'project', 'sprint', 'document', 'episode', 'entity']
          .indexOf(n.type),
      }));
      const links: GraphLink[] = data.edges || data.links || [];
      setNodeCount(nodes.length);
      renderGraph(nodes, links);
      setSelectedNode(null);
    } catch (err) {
      toast.error('Failed to hop to node neighborhood');
    } finally {
      setLoading(false);
    }
  };

  const buildGraph = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);

    try {
      const data = await ApiService.getKTGraphData(
        [projectId],
        selectedCompany?.id ? String(selectedCompany.id) : undefined,
        accessKey
      );
      
      const nodes: GraphNode[] = (data.nodes || []).map((n: any) => ({
        ...n,
        depth: ['organization', 'company', 'project', 'sprint', 'document', 'episode', 'entity']
          .indexOf(n.type),
      }));
      
      const links: GraphLink[] = data.edges || data.links || [];
      setNodeCount(nodes.length);
      
      renderGraph(nodes, links);
    } catch (err) {
      toast.error('Failed to load knowledge graph');
    } finally {
      setLoading(false);
    }
  }, [projectId, accessKey, selectedCompany]);

  // Connect to PerformanceEngine output streams
  useEffect(() => {
    let stream: EventSource | null = null;
    try {
      stream = ApiService.getNotificationStream();
      stream.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          // Only react to structural/performance changes
          if (['graph_update', 'intelligence_update', 'kt_update', 'performance_engine'].includes(payload.type)) {
            buildGraph();
          }
        } catch (e) {}
      };
    } catch (e) {
      console.error('Failed to connect to PerformanceEngine stream', e);
    }
    
    return () => {
      if (stream) stream.close();
    };
  }, [buildGraph]);

  const renderGraph = (nodes: GraphNode[], links: GraphLink[]) => {
    if (!svgRef.current || !containerRef.current) return;
    
    const container = containerRef.current;
    const W = container.clientWidth;
    const H = container.clientHeight;
    
    d3.select(svgRef.current).selectAll('*').remove();
    if (simulationRef.current) simulationRef.current.stop();
    
    const svg = d3.select(svgRef.current)
      .attr('width', W)
      .attr('height', H);
    
    const defs = svg.append('defs');
    ['#94a3b8', '#6366f1', '#10b981'].forEach((color, i) => {
      defs.append('marker')
        .attr('id', `arrow-${i}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 15)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', color);
    });

    const filter = defs.append('filter').attr('id', 'glow');
    filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur');
    const feMerge = filter.append('feMerge');
    feMerge.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    const zoomGroup = svg.append('g').attr('class', 'zoom-group');
    
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', event => {
        zoomGroup.attr('transform', event.transform);
      });
    
    svg.call(zoom);
    zoomRef.current = zoom;
    
    const simulation = d3.forceSimulation<GraphNode>(nodes)
      .force('link', d3.forceLink<GraphNode, GraphLink>(links)
        .id(d => d.id)
        .distance(d => {
          const source = d.source as GraphNode;
          const avgDepth = ((source.depth || 0)) / 2;
          return 80 + avgDepth * 40;
        })
        .strength(0.3)
      )
      .force('charge', d3.forceManyBody<GraphNode>()
        .strength((d: GraphNode) => -(NODE_CONFIG[d.type]?.radius || 8) * 15)
      )
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('radial', d3.forceRadial<GraphNode>(
        (d: GraphNode) => d.depth * 120,
        W / 2, H / 2
      ).strength(0.4))
      .force('collision', d3.forceCollide<GraphNode>()
        .radius(d => (NODE_CONFIG[d.type]?.radius || 8) + 8)
      );
    
    simulationRef.current = simulation;
    
    const link = zoomGroup.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#1e293b')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', 'url(#arrow-0)');
    
    const node = zoomGroup.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, GraphNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }) as any
      )
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelectedNode(d);
      });
    
    node.append('circle')
      .attr('r', d => NODE_CONFIG[d.type]?.radius || 8)
      .attr('fill', d => NODE_CONFIG[d.type]?.color || '#6366f1')
      .attr('stroke', d => NODE_CONFIG[d.type]?.strokeColor || '#4f46e5')
      .attr('stroke-width', 2)
      .attr('filter', d => d.depth <= 2 ? 'url(#glow)' : null);
    
    node.filter(d => d.depth <= 4)
      .append('text')
      .text(d => d.label.substring(0, 20) + (d.label.length > 20 ? '…' : ''))
      .attr('x', d => (NODE_CONFIG[d.type]?.radius || 8) + 4)
      .attr('y', 4)
      .attr('font-size', d => Math.max(8, 14 - d.depth * 1.5))
      .attr('font-weight', d => d.depth <= 2 ? '700' : '500')
      .attr('fill', '#94a3b8')
      .attr('pointer-events', 'none');
    
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as GraphNode).x!)
        .attr('y1', d => (d.source as GraphNode).y!)
        .attr('x2', d => (d.target as GraphNode).x!)
        .attr('y2', d => (d.target as GraphNode).y!);
      
      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });
    
    simulation.on('end', () => {
      const bounds = (zoomGroup.node() as SVGGElement)?.getBBox();
      if (bounds) {
        const scale = Math.min(0.9 * W / bounds.width, 0.9 * H / bounds.height, 2);
        const tx = W / 2 - scale * (bounds.x + bounds.width / 2);
        const ty = H / 2 - scale * (bounds.y + bounds.height / 2);
        svg.call(
          zoom.transform,
          d3.zoomIdentity.translate(tx, ty).scale(scale)
        );
      }
    });
  };

  useEffect(() => {
    buildGraph();
    return () => { simulationRef.current?.stop(); };
  }, [buildGraph]);

  const handleZoomIn = () => {
    if (!svgRef.current || !zoomRef.current) return;
    d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy as any, 1.3);
  };
  
  const handleZoomOut = () => {
    if (!svgRef.current || !zoomRef.current) return;
    d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy as any, 0.7);
  };

  const handleReset = () => {
    if (!svgRef.current || !containerRef.current || !zoomRef.current) return;
    const W = containerRef.current.clientWidth;
    const H = containerRef.current.clientHeight;
    d3.select(svgRef.current).transition().duration(500).call(
      zoomRef.current.transform as any, 
      d3.zoomIdentity.translate(W/2, H/2).scale(1)
    );
  };

  if (!projectId) {
    return (
      <div className="w-full h-[600px] flex flex-col items-center justify-center text-slate-500 bg-slate-950/50 rounded-[2.5rem] border border-slate-800">
        <Network size={48} className="mb-4 opacity-20 animate-pulse" />
        <p className="text-xs font-black uppercase tracking-widest text-slate-400">Select a project to explore the graph</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-[600px] bg-slate-950 rounded-[2.5rem] border border-slate-800 relative overflow-hidden group">
      {loading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="animate-spin text-indigo-500" size={36} />
            <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Mapping Concept Nodes...</p>
          </div>
        </div>
      )}

      <svg ref={svgRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      <div className="absolute top-6 left-6 flex flex-col gap-2">
        <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 p-4 rounded-2xl shadow-xl">
          <div className="flex items-center gap-2 mb-3">
            <Network size={16} className="text-indigo-400" />
            <p className="text-xs font-black uppercase tracking-widest text-white">Knowledge Graph</p>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
            <div className="flex items-center gap-2 text-[9px] font-black uppercase tracking-wider text-slate-400">
              <div className="w-2.5 h-2.5 rounded-full bg-[#6366f1]" /> Project
            </div>
            <div className="flex items-center gap-2 text-[9px] font-black uppercase tracking-wider text-slate-400">
              <div className="w-2.5 h-2.5 rounded-full bg-[#8b5cf6]" /> Sprint
            </div>
            <div className="flex items-center gap-2 text-[9px] font-black uppercase tracking-wider text-slate-400">
              <div className="w-2.5 h-2.5 rounded-full bg-[#06b6d4]" /> Document
            </div>
            <div className="flex items-center gap-2 text-[9px] font-black uppercase tracking-wider text-slate-400">
              <div className="w-2.5 h-2.5 rounded-full bg-[#ec4899]" /> Episode
            </div>
            <div className="flex items-center gap-2 text-[9px] font-black uppercase tracking-wider text-slate-400">
              <div className="w-2.5 h-2.5 rounded-full bg-[#eab308]" /> Entity
            </div>
          </div>
        </div>
      </div>

      <div className="absolute bottom-6 left-6 flex gap-2 shadow-lg z-10">
        <button 
          onClick={handleReset}
          className="p-3 bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-xl text-slate-400 hover:text-white transition-all active:scale-95"
          title="Reset Zoom & Pan"
        >
          <Maximize2 size={18} />
        </button>
        <button 
          onClick={handleZoomIn}
          className="p-3 bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-xl text-slate-400 hover:text-white transition-all active:scale-95"
          title="Zoom In"
        >
          <ZoomIn size={18} />
        </button>
        <button 
          onClick={handleZoomOut}
          className="p-3 bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-xl text-slate-400 hover:text-white transition-all active:scale-95"
          title="Zoom Out"
        >
          <ZoomOut size={18} />
        </button>
        <button 
          onClick={buildGraph}
          className="p-3 bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-xl text-slate-400 hover:text-white transition-all active:scale-95"
          title="Refresh Data"
        >
          <RefreshCw size={18} />
        </button>
      </div>

      <AnimatePresence>
        {selectedNode && (
          <motion.div 
            initial={{ x: 300, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 300, opacity: 0 }}
            className="absolute top-0 right-0 w-80 h-full bg-slate-900/90 backdrop-blur-xl border-l border-slate-800 p-8 shadow-2xl z-20 flex flex-col justify-between"
          >
            <div>
              <div className="flex justify-between items-start mb-8">
                <div className="w-12 h-12 rounded-2xl flex items-center justify-center border bg-indigo-500/20 border-indigo-500/30 text-indigo-400">
                  {selectedNode.type === 'document' ? <Layers size={24} /> : <Database size={24} />}
                </div>
                <button onClick={() => setSelectedNode(null)} className="text-slate-500 hover:text-white transition-all">
                  <AlertCircle size={20} className="rotate-45" />
                </button>
              </div>

              <h4 className="text-2xl font-black text-white mb-2 tracking-tight">{selectedNode.label}</h4>
              <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-6 bg-slate-800/40 inline-block px-2 py-0.5 rounded border border-slate-800">
                {selectedNode.type}
              </p>

              <div className="space-y-6">
                <div className="space-y-2">
                  <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Identity Details</p>
                  <p className="text-xs text-slate-300 leading-relaxed font-semibold">
                    Node ID: <code className="text-indigo-400 font-mono text-[10px]">{selectedNode.id}</code>
                  </p>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    This element represents a structured node within the active project knowledge graph.
                  </p>
                </div>
              </div>
            </div>

            
            <div className="flex gap-2">
              <button 
                onClick={hopToNode}
                className="flex-1 py-4 bg-amber-600 hover:bg-amber-500 text-white rounded-2xl font-black text-xs uppercase tracking-widest transition-all shadow-lg shadow-amber-500/20"
              >
                Hop to Node
              </button>
              <button 
                onClick={() => setSelectedNode(null)}
                className="flex-1 py-4 bg-slate-800 hover:bg-slate-700 text-white rounded-2xl font-black text-xs uppercase tracking-widest border border-slate-700 transition-all flex items-center justify-center gap-2"
              >
                Close <Info size={14} />
              </button>
            </div>

          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
