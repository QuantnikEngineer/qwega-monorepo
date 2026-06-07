import wegaLogo from "figma:asset/4733303530493ea641d669b3a7e361da54a9edf5.png";

export default function LogoLightThemePro() {
  return (
    <div className="flex items-center justify-start relative size-full" data-name="Logo Light Theme_Pro">
      <img 
        src={wegaLogo} 
        alt="WEGA Logo" 
        className="h-full w-auto object-contain"
      />
    </div>
  );
}