// Per-pest iconography for the Guide list and detail screens, and the Scan
// Result hero. Every entry sourced from the farmer guide document now has
// its own real photo; only entries with no photography fall back to a
// tinted Lucide icon.
import { Bug, ShieldCheck } from 'lucide-react';
import brownPlanthopperPhoto from '../assets/brownplanthopper.jpg';
import riceStemBorerPhoto from '../assets/ricestemborer.jpg';
import riceYellowingSyndromePhoto from '../assets/riceyellowingsyndrome.png';
import hopperburnPhoto from '../assets/hopperburn.png';
import sootyMoldPhoto from '../assets/sootymold.png';
import deadHeartPhoto from '../assets/deadheart.png';
import whiteHeadPhoto from '../assets/whitehead.png';
import stemTillersHolePhoto from '../assets/stemtillershole.png';

export const PEST_ICON_MAP = {
  bph: { icon: Bug, tint: '#8a6a2f', photo: brownPlanthopperPhoto },
  'stem-borer': { icon: Bug, tint: '#a15a2a', photo: riceStemBorerPhoto },
  'rice-yellowing-syndrome': { icon: Bug, tint: '#8a6a2f', photo: riceYellowingSyndromePhoto },
  hopperburn: { icon: Bug, tint: '#8a6a2f', photo: hopperburnPhoto },
  'sooty-mold': { icon: Bug, tint: '#8a6a2f', photo: sootyMoldPhoto },
  'dead-heart': { icon: Bug, tint: '#a15a2a', photo: deadHeartPhoto },
  'white-head': { icon: Bug, tint: '#a15a2a', photo: whiteHeadPhoto },
  'stem-tillers-hole': { icon: Bug, tint: '#a15a2a', photo: stemTillersHolePhoto },
  'bph-prevention': { icon: ShieldCheck, tint: '#8a6a2f', photo: brownPlanthopperPhoto },
  'stem-borer-prevention': { icon: ShieldCheck, tint: '#a15a2a', photo: riceStemBorerPhoto },
};

const DEFAULT_ICON = { icon: Bug, tint: '#6b6a5f' };

export function getPestIcon(id) {
  return PEST_ICON_MAP[id] || DEFAULT_ICON;
}

// Small thumbnail use (e.g. the Guide list row). Renders the real photo as
// a smooth-cornered square filling its thumbnail frame when one exists;
// otherwise falls back to the tinted vector icon so diseases/practices
// without photography still look right.
export function PestIcon({ id, size = 24, color }) {
  const { icon: Icon, tint, photo } = getPestIcon(id);
  if (photo) {
    return (
      <img
        src={photo}
        alt=""
        style={{
          width: '100%',
          height: '100%',
          borderRadius: 'inherit',
          objectFit: 'cover',
          display: 'block',
        }}
      />
    );
  }
  return <Icon size={size} color={color || tint} strokeWidth={1.8} />;
}

// Large hero use (Guide detail / Scan result banners). Renders the real
// photo filling the hero as a background image; falls back to the centered
// vector icon when no photo exists for that entry.
export function PestHeroMedia({ id, iconSize = 64 }) {
  const { icon: Icon, photo } = getPestIcon(id);
  if (photo) {
    return (
      <img
        src={photo}
        alt=""
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
        }}
      />
    );
  }
  return <Icon size={iconSize} color="rgba(255,255,255,0.9)" />;
}
