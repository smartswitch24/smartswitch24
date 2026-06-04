/**
 * OG Image generator for SmartSwitch24
 * Output: public/og-image.png  (1200 × 630)
 * Run:    node scripts/generate-og-image.mjs
 */

import sharp from 'sharp';
import { createWriteStream } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, '..', 'public', 'og-image.png');

const W = 1200;
const H = 630;

// ── Brand colours ────────────────────────────────────────────────────────────
const BLUE_DARK   = '#0d2248';
const BLUE_MID    = '#1a3a6b';
const ORANGE      = '#f57c00';
const WHITE       = '#ffffff';
const WHITE_85    = 'rgba(255,255,255,0.85)';
const WHITE_55    = 'rgba(255,255,255,0.55)';
const WHITE_10    = 'rgba(255,255,255,0.10)';
const WHITE_05    = 'rgba(255,255,255,0.05)';

// ── SVG template ─────────────────────────────────────────────────────────────
const svg = `<svg xmlns="http://www.w3.org/2000/svg"
  width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>

    <!-- Page background gradient: top-left blue → bottom-right navy -->
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"
        gradientUnits="objectBoundingBox">
      <stop offset="0%"   stop-color="${BLUE_MID}"/>
      <stop offset="100%" stop-color="${BLUE_DARK}"/>
    </linearGradient>

    <!-- Subtle shine layer top-right -->
    <radialGradient id="shine" cx="85%" cy="10%" r="55%">
      <stop offset="0%"   stop-color="rgba(255,255,255,0.06)"/>
      <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
    </radialGradient>

    <!-- Drop shadow filter for headline text -->
    <filter id="txt-shadow" x="-2%" y="-2%" width="104%" height="104%">
      <feDropShadow dx="0" dy="2" stdDeviation="6"
        flood-color="rgba(0,0,0,0.35)"/>
    </filter>

  </defs>

  <!-- ── Background ─────────────────────────────────────────────────────── -->
  <rect width="${W}" height="${H}" fill="url(#bg)"/>
  <rect width="${W}" height="${H}" fill="url(#shine)"/>

  <!-- ── Decorative geometry ────────────────────────────────────────────── -->
  <!-- Large ring: top-right -->
  <circle cx="1090" cy="-30" r="340"
    fill="none" stroke="${WHITE_05}" stroke-width="90"/>
  <!-- Medium ring: bottom-left -->
  <circle cx="60"  cy="690" r="240"
    fill="none" stroke="${WHITE_05}" stroke-width="60"/>
  <!-- Small accent dot cluster -->
  <circle cx="1140" cy="580" r="6"  fill="${WHITE_10}"/>
  <circle cx="1160" cy="555" r="4"  fill="${WHITE_10}"/>
  <circle cx="1175" cy="575" r="3"  fill="${WHITE_10}"/>

  <!-- ── Left accent bar ────────────────────────────────────────────────── -->
  <rect x="72" y="68" width="7" height="108" rx="3.5" fill="${ORANGE}"/>

  <!-- ── Logo ───────────────────────────────────────────────────────────── -->
  <!-- "Smart" -->
  <text x="96" y="148"
    font-family="'Arial Black', Arial, sans-serif"
    font-size="46" font-weight="900" fill="${WHITE}"
    letter-spacing="-0.5">Smart</text>
  <!-- "Switch" in orange -->
  <text x="253" y="148"
    font-family="'Arial Black', Arial, sans-serif"
    font-size="46" font-weight="900" fill="${ORANGE}"
    letter-spacing="-0.5">Switch</text>
  <!-- "24" -->
  <text x="462" y="148"
    font-family="'Arial Black', Arial, sans-serif"
    font-size="46" font-weight="900" fill="${WHITE}"
    letter-spacing="-0.5">24</text>

  <!-- Thin rule under logo -->
  <line x1="96" y1="172" x2="460" y2="172"
    stroke="rgba(255,255,255,0.18)" stroke-width="1"/>

  <!-- ── Main headline ──────────────────────────────────────────────────── -->
  <text x="96" y="280"
    font-family="'Arial Black', Arial, sans-serif"
    font-size="70" font-weight="900" fill="${WHITE}"
    letter-spacing="-2" filter="url(#txt-shadow)">Strom, Gas, Handy,</text>

  <text x="96" y="367"
    font-family="'Arial Black', Arial, sans-serif"
    font-size="70" font-weight="900" fill="${WHITE}"
    letter-spacing="-2" filter="url(#txt-shadow)">Reisen &amp; Finanzen</text>

  <!-- "vergleichen" in brand orange -->
  <text x="96" y="450"
    font-family="'Arial Black', Arial, sans-serif"
    font-size="58" font-weight="900" fill="${ORANGE}"
    letter-spacing="-1.5">vergleichen</text>

  <!-- ── Language badge ─────────────────────────────────────────────────── -->
  <!-- Pill background -->
  <rect x="96" y="496" width="272" height="50" rx="25"
    fill="rgba(255,255,255,0.10)" stroke="rgba(255,255,255,0.20)" stroke-width="1"/>
  <!-- Globe icon (circle + lines) -->
  <circle cx="124" cy="521" r="12"
    fill="none" stroke="${WHITE_85}" stroke-width="1.5"/>
  <ellipse cx="124" cy="521" rx="5.5" ry="12"
    fill="none" stroke="${WHITE_85}" stroke-width="1"/>
  <line x1="112" y1="521" x2="136" y2="521"
    stroke="${WHITE_85}" stroke-width="1.5"/>
  <!-- Text: Deutsch -->
  <text x="144" y="526"
    font-family="Arial, sans-serif"
    font-size="20" font-weight="600" fill="${WHITE_85}">Deutsch</text>
  <!-- Separator dot -->
  <circle cx="258" cy="522" r="3" fill="${ORANGE}"/>
  <!-- Text: Arabic word "عربي" encoded as numeric refs -->
  <text x="270" y="526"
    font-family="'Segoe UI', 'Arial Unicode MS', Arial, sans-serif"
    font-size="20" font-weight="600" fill="${WHITE_85}"
    direction="rtl" unicode-bidi="embed">&#x639;&#x631;&#x628;&#x64A;</text>

  <!-- ── Domain ─────────────────────────────────────────────────────────── -->
  <text x="1128" y="592"
    font-family="Arial, sans-serif"
    font-size="22" fill="${WHITE_55}"
    text-anchor="end">smartswitch24.de</text>

  <!-- ── Bottom accent line ─────────────────────────────────────────────── -->
  <rect x="0" y="${H - 5}" width="${W}" height="5" fill="${ORANGE}"/>

</svg>`;

// ── Render ────────────────────────────────────────────────────────────────────
await sharp(Buffer.from(svg))
  .png({ compressionLevel: 9, adaptiveFiltering: true })
  .toFile(OUT);

console.log(`✓ og-image.png written → ${OUT}`);
console.log(`  Size: ${W}×${H}px`);
