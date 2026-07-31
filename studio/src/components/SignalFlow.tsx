"use client";

import { useMemo } from "react";
import {
  Background,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import type { Device } from "@/lib/types";

/**
 * תצוגת שרשרת האותות של המכשיר.
 *
 * זו לא הדמיה: הצמתים נגזרים מהגדרת ה־pipeline של המכשיר עצמו, ושלב עם
 * gate מסומן במפורש — כדי שיהיה ברור איפה בן אדם עוצר את הזרימה.
 */

type StageData = {
  label: string;
  detail: string;
  gate: boolean;
  accent: string;
  state: "idle" | "running" | "done";
};

function StageNode({ data }: NodeProps<Node<StageData>>) {
  const border =
    data.state === "running"
      ? data.accent
      : data.gate
        ? "var(--alert)"
        : "var(--line)";

  return (
    <div
      className="w-56 rounded-lg border bg-[var(--panel-2)] px-3 py-2 text-right shadow-lg"
      style={{ borderColor: border }}
      dir="rtl"
    >
      <Handle type="target" position={Position.Right} />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-[var(--text)]">
          {data.label}
        </span>
        <span
          className="h-2 w-2 shrink-0 rounded-full"
          style={{
            background:
              data.state === "done"
                ? data.accent
                : data.state === "running"
                  ? "var(--teal)"
                  : "#3a3e45",
          }}
        />
      </div>
      <p className="mt-1 text-[11px] leading-snug text-[var(--muted)]">
        {data.detail}
      </p>
      {data.gate ? (
        <p className="mt-1.5 text-[10px] text-[var(--alert)]">
          עצירה לאישור אנושי
        </p>
      ) : null}
      <Handle type="source" position={Position.Left} />
    </div>
  );
}

const nodeTypes = { stage: StageNode };

export function SignalFlow({
  device,
  state,
}: {
  device: Device;
  /** idle = טרם הורץ, running = בעיצומה, done = הושלם */
  state: "idle" | "running" | "done";
}) {
  const nodes = useMemo<Node<StageData>[]>(
    () =>
      device.pipeline.map((stage, index) => ({
        id: stage.id,
        type: "stage",
        // RTL: השלב הראשון בימין, ולכן הציר מתקדם שמאלה
        position: { x: -index * 270, y: (index % 2) * 46 },
        data: {
          label: stage.label,
          detail: stage.detail,
          gate: Boolean(stage.gate),
          accent: device.accent,
          state,
        },
        draggable: true,
      })),
    [device, state],
  );

  const edges = useMemo<Edge[]>(
    () =>
      device.pipeline.slice(1).map((stage, index) => ({
        id: `${device.pipeline[index].id}->${stage.id}`,
        source: device.pipeline[index].id,
        target: stage.id,
        animated: state === "running",
      })),
    [device, state],
  );

  return (
    <div className="h-[320px] w-full overflow-hidden rounded-xl border border-[var(--line)] bg-[#0b0c0e]">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        nodesConnectable={false}
        edgesFocusable={false}
        minZoom={0.3}
      >
        <Background color="#22262c" gap={22} size={1} />
      </ReactFlow>
    </div>
  );
}
