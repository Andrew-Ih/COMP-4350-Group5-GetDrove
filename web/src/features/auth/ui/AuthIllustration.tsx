/**
 * The night scene from the sign-up mockup: city skyline, the campus building under the
 * moon, and a car of students on the dotted route to campus. Decorative only.
 *
 * Drawn in a 1200 × 1000 box and anchored to the bottom centre, so narrow screens show
 * the car and wide screens show the whole scene.
 */

const STARS: Array<[number, number, number]> = [
  [130, 90, 4], [420, 60, 3], [610, 150, 4], [880, 110, 3], [1150, 70, 4], [260, 250, 3],
  [520, 300, 4], [760, 250, 3], [1080, 330, 3], [60, 380, 3], [350, 420, 4], [690, 400, 3],
  [930, 470, 4], [1160, 460, 3], [210, 520, 3],
];

const ROUTE_BEHIND = Array.from({ length: 12 }, (_, i) => [20 + i * 34, 745 - i * 1.2] as const);
const ROUTE_AHEAD = [
  [1012, 690],
  [1036, 662],
  [1058, 634],
  [1080, 606],
] as const;

const COLUMNS = Array.from({ length: 9 }, (_, i) => 740 + i * 48);

function Rider({ x, skin, top, hat }: { x: number; skin: string; top: string; hat?: string }) {
  return (
    <g>
      <ellipse cx={x} cy={700} rx={34} ry={36} fill={top} />
      <circle cx={x} cy={652} r={22} fill={skin} />
      {hat ? (
        <>
          <path d={`M ${x - 23} 650 a 23 23 0 0 1 46 0 z`} fill={hat} />
          <circle cx={x} cy={622} r={6} fill={hat} />
        </>
      ) : (
        <path d={`M ${x - 22} 648 a 22 20 0 0 1 44 0 q -22 -8 -44 0 z`} fill="#2a2a2a" />
      )}
    </g>
  );
}

export function AuthIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 1200 1000"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
      className={className}
    >
      <rect width="1200" height="1000" fill="#111111" />

      {STARS.map(([x, y, r]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r={r} fill="#ffffff" opacity={0.85} />
      ))}
      <circle cx={1000} cy={250} r={95} fill="#d6d6d6" />

      {/* City skyline */}
      <g fill="#1d1d1d">
        <rect x={0} y={500} width={95} height={220} />
        <rect x={105} y={540} width={80} height={180} />
        <rect x={195} y={440} width={70} height={280} />
        <rect x={275} y={520} width={110} height={200} />
        <rect x={395} y={470} width={75} height={250} />
        <rect x={480} y={560} width={150} height={160} />
      </g>

      {/* Campus building */}
      <g fill="#262626">
        <rect x={870} y={360} width={140} height={110} />
        <path d="M 870 362 a 70 70 0 0 1 140 0 z" />
        <polygon points="680,530 940,440 1200,530" />
        <rect x={700} y={528} width={500} height={192} />
      </g>
      {COLUMNS.map((x) => (
        <rect key={x} x={x} y={548} width={16} height={160} fill="#333333" />
      ))}
      <rect x={918} y={610} width={44} height={110} fill="#161616" />

      {/* Snowy ground and the road */}
      <path d="M 0 700 C 300 660 600 715 900 680 S 1200 650 1200 650 L 1200 770 L 0 770 Z" fill="#f1f1ef" />
      <path d="M 0 770 L 1200 740 L 1200 1000 L 0 1000 Z" fill="#161616" />
      <line x1={0} y1={905} x2={1200} y2={880} stroke="#8f8f8f" strokeWidth={6} strokeDasharray="44 30" />

      {/* Route behind the car, then ahead of it to the pickup point */}
      {ROUTE_BEHIND.map(([x, y]) => (
        <circle key={x} cx={x} cy={y} r={9} fill="#0e7c3a" />
      ))}
      {ROUTE_AHEAD.map(([x, y]) => (
        <circle key={x} cx={x} cy={y} r={8} fill="#0e7c3a" />
      ))}
      <circle cx={1112} cy={566} r={34} fill="#0e7c3a" />
      <circle cx={1112} cy={566} r={13} fill="#ffffff" />

      {/* The car */}
      <ellipse cx={720} cy={925} rx={340} ry={18} fill="#0a0a0a" />
      <path d="M 470 705 L 565 600 Q 580 585 605 585 L 860 585 Q 890 585 905 605 L 985 705 Z" fill="#ffffff" />
      <polygon points="525,700 592,618 705,618 705,700" fill="#1a1a1a" />
      <polygon points="725,618 858,618 918,700 725,700" fill="#1a1a1a" />
      <Rider x={585} skin="#8d5a3b" top="#3a3a3a" />
      <Rider x={655} skin="#ecdcc8" top="#e6e6e6" hat="#0e7c3a" />
      <Rider x={780} skin="#c58c63" top="#0e7c3a" />
      <Rider x={858} skin="#6b4630" top="#d9d9d9" />
      <rect x={430} y={698} width={600} height={170} rx={30} fill="#ffffff" />
      <rect x={585} y={735} width={56} height={9} rx={4.5} fill="#c9c9c9" />
      <rect x={790} y={735} width={56} height={9} rx={4.5} fill="#c9c9c9" />
      <rect x={430} y={740} width={20} height={28} rx={3} fill="#0e7c3a" />
      <polygon points="985,748 1018,744 1022,776 990,774" fill="#ffffff" stroke="#b5b5b5" strokeWidth={3} />
      <circle cx={565} cy={868} r={64} fill="#111111" />
      <circle cx={565} cy={868} r={27} fill="#8a8a8a" />
      <circle cx={895} cy={868} r={64} fill="#111111" />
      <circle cx={895} cy={868} r={27} fill="#8a8a8a" />
    </svg>
  );
}
