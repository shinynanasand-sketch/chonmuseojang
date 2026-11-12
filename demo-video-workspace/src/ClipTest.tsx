import { AbsoluteFill, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import captions from "../captions.json";

const linesOf = (caption: string, captionLines?: string[]): string[] => {
  if (captionLines && captionLines.length > 0) {
    return captionLines.slice(0, 2);
  }
  const parts = caption.split(/(?<=다\.)\s+/).filter(Boolean);
  return parts.slice(0, 2);
};

const readLines = (scene: { caption: string; captionLines?: string[] }) => {
  return linesOf(scene.caption, "captionLines" in scene ? scene.captionLines : undefined);
};

const spansOf = (item: { startSec: number | null; endSec: number | null; spans?: { startSec: number; endSec: number }[] }) => {
  if (item.spans && item.spans.length > 0) {
    return item.spans;
  }
  if (item.startSec !== null && item.endSec !== null) {
    return [{ startSec: item.startSec, endSec: item.endSec }];
  }
  return [];
};

const RoleAndCaption: React.FC<{ role: string; lines: string[] }> = ({ role, lines }) => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    <div
      style={{
        position: "absolute",
        top: 108,
        right: 36,
        padding: "8px 16px",
        background: "rgba(0, 0, 0, 0.72)",
        color: "white",
        fontSize: 30,
        lineHeight: 1.2,
      }}
    >
      {role}
    </div>
    {lines.length > 0 ? (
      <div
        style={{
          position: "absolute",
          left: 16,
          width: 544,
          bottom: 96,
          padding: "12px 16px",
          background: "rgba(0, 0, 0, 0.78)",
          color: "white",
          fontSize: 28,
          lineHeight: 1.35,
          textAlign: "center",
        }}
      >
        {lines.map((line) => (
          <div key={line}>{line}</div>
        ))}
      </div>
    ) : null}
  </AbsoluteFill>
);

export const ClipTest: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const originalSec = captions.test.startSec + frame / fps;
  const scene = captions.scenes.find((item) => {
    return item.id.startsWith("A-") && spansOf(item).some((span) => originalSec >= span.startSec && originalSec < span.endSec);
  });
  const lines = scene ? readLines(scene) : [];

  return (
    <AbsoluteFill style={{ backgroundColor: "black", fontFamily: '"Malgun Gothic", sans-serif' }}>
      <OffthreadVideo src={staticFile("A.mp4")} startFrom={Math.round(captions.test.startSec * fps)} />
      <RoleAndCaption role={captions.test.roleLabel} lines={lines} />
    </AbsoluteFill>
  );
};

export const clipBLengths = (fps: number) =>
  captions.b.test.segments.map((seg) => Math.round((seg.endSec - seg.startSec) * fps));

const originalSecAt = (frame: number, fps: number) => {
  const segments = captions.b.test.segments;
  const lengths = clipBLengths(fps);
  let left = frame;
  for (let i = 0; i < segments.length; i++) {
    if (left < lengths[i]) {
      return segments[i].startSec + left / fps;
    }
    left -= lengths[i];
  }
  return segments[segments.length - 1].endSec;
};

export const ClipBTest: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lengths = clipBLengths(fps);
  const originalSec = originalSecAt(frame, fps);
  const scene = captions.scenes.find((item) => {
    return item.id.startsWith("B-") && spansOf(item).some((span) => originalSec >= span.startSec && originalSec < span.endSec);
  });
  const lines = scene ? readLines(scene) : [];
  let from = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "black", fontFamily: '"Malgun Gothic", sans-serif' }}>
      {captions.b.test.segments.map((seg, i) => {
        const node = (
          <Sequence key={`${seg.startSec}-${seg.endSec}`} from={from} durationInFrames={lengths[i]}>
            <OffthreadVideo src={staticFile(captions.b.original.file)} startFrom={Math.round(seg.startSec * fps)} />
          </Sequence>
        );
        from += lengths[i];
        return node;
      })}
      <RoleAndCaption role={captions.b.test.roleLabel} lines={lines} />
    </AbsoluteFill>
  );
};

export const clipCLengths = (fps: number) =>
  captions.c.test.segments.map((seg) => Math.round((seg.endSec - seg.startSec) * fps));

const originalSecAtC = (frame: number, fps: number) => {
  const segments = captions.c.test.segments;
  const lengths = clipCLengths(fps);
  let left = frame;
  for (let i = 0; i < segments.length; i++) {
    if (left < lengths[i]) {
      return segments[i].startSec + left / fps;
    }
    left -= lengths[i];
  }
  return segments[segments.length - 1].endSec;
};

export const ClipCTest: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lengths = clipCLengths(fps);
  const originalSec = originalSecAtC(frame, fps);
  const scene = captions.scenes.find((item) => {
    return item.id.startsWith("C-") && spansOf(item).some((span) => originalSec >= span.startSec && originalSec < span.endSec);
  });
  const lines = scene ? readLines(scene) : [];
  let from = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "black", fontFamily: '"Malgun Gothic", sans-serif' }}>
      {captions.c.test.segments.map((seg, i) => {
        const node = (
          <Sequence key={`${seg.startSec}-${seg.endSec}`} from={from} durationInFrames={lengths[i]}>
            <OffthreadVideo src={staticFile(captions.c.original.file)} startFrom={Math.round(seg.startSec * fps)} />
          </Sequence>
        );
        from += lengths[i];
        return node;
      })}
      <RoleAndCaption role={captions.c.test.roleLabel} lines={lines} />
    </AbsoluteFill>
  );
};

export const clipDLengths = (fps: number) =>
  captions.d.test.segments.map((seg) => Math.round((seg.endSec - seg.startSec) * fps));

const originalSecAtD = (frame: number, fps: number) => {
  const segments = captions.d.test.segments;
  const lengths = clipDLengths(fps);
  let left = frame;
  for (let i = 0; i < segments.length; i++) {
    if (left < lengths[i]) {
      return segments[i].startSec + left / fps;
    }
    left -= lengths[i];
  }
  return segments[segments.length - 1].endSec;
};

export const ClipDTest: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lengths = clipDLengths(fps);
  const originalSec = originalSecAtD(frame, fps);
  const scene = captions.scenes.find((item) => {
    return item.id.startsWith("D-") && spansOf(item).some((span) => originalSec >= span.startSec && originalSec < span.endSec);
  });
  const lines = scene ? readLines(scene) : [];
  let from = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "black", fontFamily: '"Malgun Gothic", sans-serif' }}>
      {captions.d.test.segments.map((seg, i) => {
        const node = (
          <Sequence key={`${seg.startSec}-${seg.endSec}`} from={from} durationInFrames={lengths[i]}>
            <OffthreadVideo src={staticFile(captions.d.original.file)} startFrom={Math.round(seg.startSec * fps)} />
          </Sequence>
        );
        from += lengths[i];
        return node;
      })}
      <RoleAndCaption role={captions.d.test.roleLabel} lines={lines} />
    </AbsoluteFill>
  );
};

export const clipELengths = (fps: number) =>
  captions.e.test.segments.map((seg) => Math.round((seg.endSec - seg.startSec) * fps));

const originalSecAtE = (frame: number, fps: number) => {
  const segments = captions.e.test.segments;
  const lengths = clipELengths(fps);
  let left = frame;
  for (let i = 0; i < segments.length; i++) {
    if (left < lengths[i]) {
      return segments[i].startSec + left / fps;
    }
    left -= lengths[i];
  }
  return segments[segments.length - 1].endSec;
};

const roleAtE = (originalSec: number) => {
  const span = captions.e.test.roleSpans.find((item) => originalSec >= item.startSec && originalSec < item.endSec);
  return span ? span.roleLabel : captions.e.test.roleLabel;
};

export const ClipETest: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lengths = clipELengths(fps);
  const originalSec = originalSecAtE(frame, fps);
  const scene = captions.scenes.find((item) => {
    return item.id.startsWith("E-") && spansOf(item).some((span) => originalSec >= span.startSec && originalSec < span.endSec);
  });
  const lines = scene ? readLines(scene) : [];
  let from = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "black", fontFamily: '"Malgun Gothic", sans-serif' }}>
      {captions.e.test.segments.map((seg, i) => {
        const node = (
          <Sequence key={`${seg.startSec}-${seg.endSec}`} from={from} durationInFrames={lengths[i]}>
            <OffthreadVideo src={staticFile(captions.e.original.file)} startFrom={Math.round(seg.startSec * fps)} />
          </Sequence>
        );
        from += lengths[i];
        return node;
      })}
      <RoleAndCaption role={roleAtE(originalSec)} lines={lines} />
    </AbsoluteFill>
  );
};

export const clipFLengths = (fps: number) =>
  captions.f.test.segments.map((seg) => Math.round((seg.endSec - seg.startSec) * fps));

const originalSecAtF = (frame: number, fps: number) => {
  const segments = captions.f.test.segments;
  const lengths = clipFLengths(fps);
  let left = frame;
  for (let i = 0; i < segments.length; i++) {
    if (left < lengths[i]) {
      return segments[i].startSec + left / fps;
    }
    left -= lengths[i];
  }
  return segments[segments.length - 1].endSec;
};

const roleAtF = (originalSec: number) => {
  const span = captions.f.test.roleSpans.find((item) => originalSec >= item.startSec && originalSec < item.endSec);
  return span ? span.roleLabel : captions.f.test.roleLabel;
};

export const ClipFTest: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lengths = clipFLengths(fps);
  const originalSec = originalSecAtF(frame, fps);
  const scene = captions.scenes.find((item) => {
    return item.id.startsWith("F-") && spansOf(item).some((span) => originalSec >= span.startSec && originalSec < span.endSec);
  });
  const lines = scene ? readLines(scene) : [];
  let from = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "black", fontFamily: '"Malgun Gothic", sans-serif' }}>
      {captions.f.test.segments.map((seg, i) => {
        const node = (
          <Sequence key={`${seg.startSec}-${seg.endSec}`} from={from} durationInFrames={lengths[i]}>
            <OffthreadVideo src={staticFile(captions.f.original.file)} startFrom={Math.round(seg.startSec * fps)} />
          </Sequence>
        );
        from += lengths[i];
        return node;
      })}
      <RoleAndCaption role={roleAtF(originalSec)} lines={lines} />
    </AbsoluteFill>
  );
};
