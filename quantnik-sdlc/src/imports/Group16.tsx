import { imgFrame } from "./svg-w2q61";

function Frame() {
  return (
    <div className="absolute h-[74px] left-0 top-0 w-[398px]" data-name="Frame">
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