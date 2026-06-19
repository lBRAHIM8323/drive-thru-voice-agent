import type { ComponentProps, CSSProperties } from 'react';
import {
  BarVisualizer,
  useMultibandTrackVolume,
  type AgentState,
} from '@livekit/components-react';

import type { Visualizer } from '../api/types';

// Use the exact track-reference type BarVisualizer accepts (also valid input
// for useMultibandTrackVolume), avoiding internal type-name imports.
type AudioTrack = ComponentProps<typeof BarVisualizer>['trackRef'];

export interface VisualizerProps {
  variant: Visualizer;
  audioTrack: AudioTrack;
  state: AgentState;
  accentColor?: string;
}

const DEFAULT_ACCENT = '#4dabf7';

// State-based opacity so the visualizer "settles" while idle/listening and
// comes alive while the agent speaks.
function stateOpacity(state: AgentState): number {
  switch (state) {
    case 'speaking':
      return 1;
    case 'thinking':
      return 0.85;
    case 'listening':
      return 0.6;
    default:
      return 0.35;
  }
}

export function AgentVisualizer({ variant, audioTrack, state, accentColor }: VisualizerProps) {
  const color = accentColor || DEFAULT_ACCENT;
  switch (variant) {
    case 'grid':
      return <GridVis audioTrack={audioTrack} state={state} color={color} />;
    case 'radial':
      return <RadialVis audioTrack={audioTrack} state={state} color={color} />;
    case 'wave':
      return <WaveVis audioTrack={audioTrack} state={state} color={color} />;
    case 'aura':
      return <AuraVis audioTrack={audioTrack} state={state} color={color} />;
    case 'bar':
    default:
      return (
        <div style={{ width: 240, height: 240, opacity: stateOpacity(state) }}>
          <BarVisualizer
            state={state}
            barCount={7}
            trackRef={audioTrack}
            options={{ minHeight: 8 }}
            style={{ width: '100%', height: '100%', '--lk-fg': color } as CSSProperties}
          />
        </div>
      );
  }
}

interface SubProps {
  audioTrack: AudioTrack;
  state: AgentState;
  color: string;
}

function GridVis({ audioTrack, state, color }: SubProps) {
  const cols = 7;
  const rows = 7;
  const volumes = useMultibandTrackVolume(audioTrack, { bands: cols });
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap: 6,
        width: 240,
        height: 240,
        opacity: stateOpacity(state),
      }}
    >
      {Array.from({ length: rows * cols }).map((_, idx) => {
        const col = idx % cols;
        const row = Math.floor(idx / cols);
        const level = volumes[col] ?? 0;
        // A cell lights up when the column's level reaches its row height.
        const lit = level * rows >= rows - row;
        return (
          <div
            key={idx}
            style={{
              borderRadius: 4,
              background: lit ? color : 'var(--mantine-color-default-border)',
              opacity: lit ? 0.5 + level * 0.5 : 0.25,
              transition: 'opacity 80ms linear, background 80ms linear',
            }}
          />
        );
      })}
    </div>
  );
}

function RadialVis({ audioTrack, state, color }: SubProps) {
  const bands = 32;
  const volumes = useMultibandTrackVolume(audioTrack, { bands });
  const size = 240;
  const cx = size / 2;
  const cy = size / 2;
  const inner = 52;
  return (
    <svg width={size} height={size} style={{ opacity: stateOpacity(state) }}>
      <circle cx={cx} cy={cy} r={inner - 8} fill="none" stroke={color} strokeWidth={2} opacity={0.4} />
      {volumes.map((v, i) => {
        const angle = (i / bands) * Math.PI * 2 - Math.PI / 2;
        const len = inner + 8 + v * 60;
        return (
          <line
            key={i}
            x1={cx + Math.cos(angle) * inner}
            y1={cy + Math.sin(angle) * inner}
            x2={cx + Math.cos(angle) * len}
            y2={cy + Math.sin(angle) * len}
            stroke={color}
            strokeWidth={3}
            strokeLinecap="round"
          />
        );
      })}
    </svg>
  );
}

function WaveVis({ audioTrack, state, color }: SubProps) {
  const bands = 48;
  const volumes = useMultibandTrackVolume(audioTrack, { bands });
  const width = 320;
  const height = 140;
  const mid = height / 2;
  const step = width / (bands - 1);
  const points = volumes
    .map((v, i) => `${i * step},${mid - (v - 0.0) * mid * 0.9 * (i % 2 ? 1 : -1)}`)
    .join(' ');
  return (
    <svg width={width} height={height} style={{ opacity: stateOpacity(state) }}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={3}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

function AuraVis({ audioTrack, state, color }: SubProps) {
  const volumes = useMultibandTrackVolume(audioTrack, { bands: 5 });
  const avg = volumes.reduce((a, b) => a + b, 0) / (volumes.length || 1);
  const scale = 0.85 + avg * 0.5;
  return (
    <div
      style={{
        width: 240,
        height: 240,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: stateOpacity(state),
      }}
    >
      <div
        style={{
          width: 160,
          height: 160,
          borderRadius: '50%',
          background: `radial-gradient(circle at 50% 45%, ${color}, transparent 70%)`,
          filter: 'blur(8px)',
          transform: `scale(${scale})`,
          transition: 'transform 90ms ease-out',
        }}
      />
    </div>
  );
}
