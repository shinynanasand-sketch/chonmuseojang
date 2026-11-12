import { Composition } from "remotion";
import captions from "../captions.json";
import { ClipBTest, ClipCTest, ClipDTest, ClipETest, ClipFTest, ClipTest, clipBLengths, clipCLengths, clipDLengths, clipELengths, clipFLengths } from "./ClipTest";

const fps = captions.original.fps;
const durationInFrames = Math.round((captions.test.endSec - captions.test.startSec) * fps);
const bFps = captions.b.original.fps;
const bDuration = clipBLengths(bFps).reduce((sum, frames) => sum + frames, 0);
const cFps = captions.c.original.fps;
const cDuration = clipCLengths(cFps).reduce((sum, frames) => sum + frames, 0);
const dFps = captions.d.original.fps;
const dDuration = clipDLengths(dFps).reduce((sum, frames) => sum + frames, 0);
const eFps = captions.e.original.fps;
const eDuration = clipELengths(eFps).reduce((sum, frames) => sum + frames, 0);
const fFps = captions.f.original.fps;
const fDuration = clipFLengths(fFps).reduce((sum, frames) => sum + frames, 0);

export const RemotionRoot = () => {
  return (
    <>
      <Composition
        id="ClipATest"
        component={ClipTest}
        durationInFrames={durationInFrames}
        fps={fps}
        width={captions.original.width}
        height={captions.original.height}
      />
      <Composition
        id="ClipBTest"
        component={ClipBTest}
        durationInFrames={bDuration}
        fps={bFps}
        width={captions.b.original.width}
        height={captions.b.original.height}
      />
      <Composition
        id="ClipCTest"
        component={ClipCTest}
        durationInFrames={cDuration}
        fps={cFps}
        width={captions.c.original.width}
        height={captions.c.original.height}
      />
      <Composition
        id="ClipDTest"
        component={ClipDTest}
        durationInFrames={dDuration}
        fps={dFps}
        width={captions.d.original.width}
        height={captions.d.original.height}
      />
      <Composition
        id="ClipETest"
        component={ClipETest}
        durationInFrames={eDuration}
        fps={eFps}
        width={captions.e.original.width}
        height={captions.e.original.height}
      />
      <Composition
        id="ClipFTest"
        component={ClipFTest}
        durationInFrames={fDuration}
        fps={fFps}
        width={captions.f.original.width}
        height={captions.f.original.height}
      />
    </>
  );
};
