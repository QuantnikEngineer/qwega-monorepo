import svgPaths from "./svg-akow466mw8";

function Group7() {
  return (
    <div className="absolute bottom-0 left-0 right-[69.36%] top-0">
      <svg className="block size-full" fill="none" preserveAspectRatio="none" viewBox="0 0 80 32">
        <g id="Group 7">
          <path d={svgPaths.p1b2ee380} fill="var(--fill-0, white)" id="Vector" />
          <path d={svgPaths.p154e5100} fill="var(--fill-0, white)" id="Vector_2" />
          <path d={svgPaths.p2956cb80} fill="var(--fill-0, white)" id="Vector_3" />
          <path d={svgPaths.p1460fbf0} fill="var(--fill-0, white)" id="Vector_4" />
          <path d={svgPaths.p1e419b80} fill="var(--fill-0, white)" id="Vector_5" />
          <path d={svgPaths.p3a105750} fill="var(--fill-0, white)" id="Vector_6" />
          <path d={svgPaths.p3c900400} fill="var(--fill-0, white)" id="Vector_7" />
          <path d={svgPaths.p24ddc400} fill="var(--fill-0, white)" id="Vector_8" />
        </g>
      </svg>
    </div>
  );
}

function Group8() {
  return (
    <div className="absolute aspect-[169.42/22.0018] bottom-[15.18%] left-[90px] top-[15.71%]">
      <svg className="block size-full" fill="none" preserveAspectRatio="none" viewBox="0 0 170 22">
        <g id="Group 8">
          <path d={svgPaths.p1beea600} fill="url(#paint0_linear_6023_441)" id="Vector" />
          <path d={svgPaths.p30891b00} fill="url(#paint1_linear_6023_441)" id="Vector_2" />
          <path d={svgPaths.p3b036780} fill="url(#paint2_linear_6023_441)" id="Vector_3" />
        </g>
        <defs>
          <linearGradient gradientUnits="userSpaceOnUse" id="paint0_linear_6023_441" x1="9.44465e-08" x2="53.747" y1="0.313451" y2="17.0599">
            <stop stopColor="#49D8FF" />
            <stop offset="1" stopColor="#8376FF" />
          </linearGradient>
          <linearGradient gradientUnits="userSpaceOnUse" id="paint1_linear_6023_441" x1="61.4728" x2="76.4728" y1="0.0236212" y2="18.7189">
            <stop offset="0.552367" stopColor="#E82F82" />
            <stop offset="1" stopColor="#F57F2A" />
          </linearGradient>
          <linearGradient gradientUnits="userSpaceOnUse" id="paint2_linear_6023_441" x1="83.2083" x2="165.022" y1="0.418354" y2="32.7376">
            <stop stopColor="#49D8FF" />
            <stop offset="1" stopColor="#8376FF" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}

function Group9() {
  return (
    <div className="absolute aspect-[259.42/31.8335] bottom-0 contents left-0 top-0">
      <Group7 />
      <Group8 />
    </div>
  );
}

export default function DarkThemeLogo() {
  return (
    <div className="relative size-full" data-name="Dark Theme Logo">
      <Group9 />
    </div>
  );
}