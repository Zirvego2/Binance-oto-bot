const COLORS = ["#f5c518", "#22c55e", "#eab308", "#fbbf24", "#4ade80", "#fde047"];

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  color: string;
  rotation: number;
  spin: number;
  life: number;
}

/** Kar al (TP) aninda tam ekran konfeti patlatir. */
export function fireTakeProfitConfetti(): void {
  if (typeof window === "undefined") return;

  const canvas = document.createElement("canvas");
  canvas.style.position = "fixed";
  canvas.style.inset = "0";
  canvas.style.width = "100%";
  canvas.style.height = "100%";
  canvas.style.pointerEvents = "none";
  canvas.style.zIndex = "9999";
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  document.body.appendChild(canvas);

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    canvas.remove();
    return;
  }

  const particles: Particle[] = Array.from({ length: 220 }, () => ({
    x: window.innerWidth * (0.2 + Math.random() * 0.6),
    y: window.innerHeight * (0.25 + Math.random() * 0.2),
    vx: (Math.random() - 0.5) * 18,
    vy: Math.random() * -20 - 6,
    size: Math.random() * 10 + 5,
    color: COLORS[Math.floor(Math.random() * COLORS.length)] ?? "#f5c518",
    rotation: Math.random() * Math.PI,
    spin: (Math.random() - 0.5) * 0.3,
    life: 1,
  }));

  let frame = 0;
  const maxFrames = 150;

  const tick = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.35;
      p.vx *= 0.99;
      p.rotation += p.spin;
      p.life = Math.max(0, p.life - 0.008);

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rotation);
      ctx.globalAlpha = p.life;
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
      ctx.restore();
    }

    frame += 1;
    if (frame < maxFrames) {
      requestAnimationFrame(tick);
    } else {
      canvas.remove();
    }
  };

  requestAnimationFrame(tick);
}
