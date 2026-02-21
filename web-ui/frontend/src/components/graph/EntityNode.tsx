import { memo } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { User, MapPin, Building2, Lightbulb, Calendar, HelpCircle, type LucideProps } from "lucide-react";
import { cn } from "@/lib/utils";

export const TYPE_COLORS: Record<string, string> = {
  person: "#7c6ef0",
  place: "#4caf50",
  organization: "#ff9800",
  concept: "#2196f3",
  event: "#ef5350",
  default: "#6b70a0",
};

const TYPE_ICONS: Record<string, React.ComponentType<LucideProps>> = {
  person: User,
  place: MapPin,
  organization: Building2,
  concept: Lightbulb,
  event: Calendar,
};

export type EntityNodeData = {
  label: string;
  entityType: string;
  connectionCount: number;
};

type EntityNodeType = Node<EntityNodeData, "entity">;

function EntityNodeComponent({ data, selected }: NodeProps<EntityNodeType>) {
  const color = TYPE_COLORS[data.entityType || "default"] || TYPE_COLORS.default;
  const Icon = TYPE_ICONS[data.entityType] || HelpCircle;

  const size = Math.max(36, Math.min(56, 36 + (data.connectionCount || 0) * 3));

  return (
    <>
      <Handle type="target" position={Position.Top} className="!bg-transparent !border-0 !w-0 !h-0" />
      <div
        className={cn(
          "flex flex-col items-center gap-1 cursor-pointer transition-all duration-150",
          selected && "scale-110",
        )}
      >
        <div
          className={cn(
            "rounded-full flex items-center justify-center text-white shadow-md transition-shadow duration-150",
            selected && "ring-2 ring-ring ring-offset-2 ring-offset-background",
            "hover:shadow-lg",
          )}
          style={{
            backgroundColor: color,
            width: size,
            height: size,
          }}
        >
          <Icon className="text-white" size={Math.round(size * 0.45)} />
        </div>
        <span
          className={cn(
            "text-[11px] font-medium text-foreground max-w-[90px] truncate text-center leading-tight",
            selected && "font-semibold",
          )}
        >
          {data.label}
        </span>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-transparent !border-0 !w-0 !h-0" />
    </>
  );
}

export const EntityNode = memo(EntityNodeComponent);
