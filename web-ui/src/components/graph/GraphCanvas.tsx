import { useCallback, useEffect, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphNode, GraphEdge } from "@/api/client";

const TYPE_COLORS: Record<string, string> = {
  person: "#7c6ef0",
  place: "#4caf50",
  organization: "#ff9800",
  concept: "#2196f3",
  event: "#ef5350",
  default: "#6b70a0",
};

function toReactFlowNodes(graphNodes: GraphNode[]): Node[] {
  return graphNodes.map((n, i) => ({
    id: n.id,
    data: {
      label: n.name,
      type: n.type,
    },
    position: {
      x: 200 + Math.cos((i / graphNodes.length) * 2 * Math.PI) * 300,
      y: 200 + Math.sin((i / graphNodes.length) * 2 * Math.PI) * 300,
    },
    style: {
      background: TYPE_COLORS[n.type || "default"] || TYPE_COLORS.default,
      color: "#fff",
      borderRadius: "12px",
      padding: "8px 14px",
      fontSize: "12px",
      fontWeight: "600",
      border: "none",
    },
  }));
}

function toReactFlowEdges(graphEdges: GraphEdge[]): Edge[] {
  return graphEdges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target,
    label: e.label,
    type: "default",
    style: { stroke: "#4a4e70", strokeWidth: 1.5 },
    labelStyle: { fontSize: 10, fill: "#9fa3c2" },
  }));
}

interface GraphCanvasProps {
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  onNodeClick?: (name: string) => void;
}

export function GraphCanvas({ graphNodes, graphEdges, onNodeClick }: GraphCanvasProps) {
  const initialNodes = useMemo(() => toReactFlowNodes(graphNodes), [graphNodes]);
  const initialEdges = useMemo(() => toReactFlowEdges(graphEdges), [graphEdges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(toReactFlowNodes(graphNodes));
    setEdges(toReactFlowEdges(graphEdges));
  }, [graphNodes, graphEdges, setNodes, setEdges]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeClick?.(node.data.label as string);
    },
    [onNodeClick],
  );

  return (
    <div className="w-full h-full bg-surface">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#232640" gap={24} />
        <Controls
          style={{ background: "#171923", borderColor: "#2d3148", borderRadius: "8px" }}
        />
      </ReactFlow>
    </div>
  );
}
