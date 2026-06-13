import { imgFrame } from "./svg-h8px2";

function Frame() {
  return (
    <div className="absolute h-8 left-0 top-0 w-[172.108px]" data-name="Frame">
      <img className="block max-w-none size-full" src={imgFrame} />
    </div>
  );
}

export default function Group16() {
  return (
    <div className="relative size-full">
      <Frame />
    </div>
  );
}