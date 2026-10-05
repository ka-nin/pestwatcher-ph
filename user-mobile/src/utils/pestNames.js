// Primary name follows the selected language; the other language's name is
// the secondary line beneath it. Hopperburn has the same name in both, so
// the secondary line is dropped when it would just repeat the primary.
export function pestNames(entry, language) {
  const en = entry.nameEn || entry.name;
  const fil = entry.nameFil;
  const [primary, secondary] = language === 'en' ? [en, fil] : [fil, en];
  return { primary, secondary: secondary === primary ? '' : secondary };
}
