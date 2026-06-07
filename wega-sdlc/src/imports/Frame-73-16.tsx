import { imgFrame } from "./svg-ooayi";

export default function Frame() {
  return (
    <div className="relative size-full" data-name="Frame">
      <img className="block max-w-none size-full" src={imgFrame} />
    </div>
  );
}