// Mock data standing in for the FastAPI backend responses described in
// backend/README.md. Shapes here should match the real API contract so
// swapping in real fetch calls later is a drop-in replacement.

export const currentLocation = {
  province: 'Nueva Ecija',
  region: 'Central Luzon',
};

export const dashboardSummary = {
  riskLevel: 'low', // 'low' | 'medium' | 'high'
  riskLabelFil: 'Mababang Panganib',
  pestFil: 'Kayumangging Hanip at Aksip',
  message:
    'Mababa ang posibilidad ng pagtaas ng peste sa loob ng dalawang linggo. Ipagpatuloy ang normal na pagmamanman. Hindi kinakailangan ang agarang pag-ispray ng pestisidyo.',
  tip: 'I-check ang dahon, puno, at dami ng peste bago mag-apply ng anumang kemikal.',
  weather: {
    temperature: { value: 29.7, unit: '°C', feelsLike: 36, label: 'Feels 36°C' },
    rainfall: { value: 178, unit: 'mm', label: 'Last 24h' },
    humidity: { value: 91, unit: '%', label: 'Very High' },
  },
  trend: [
    { day: 'Mon', level: 1 },
    { day: 'Tue', level: 1 },
    { day: 'Wed', level: 2 },
    { day: 'Thu', level: 2 },
    { day: 'Fri', level: 2 },
    { day: 'Sat', level: 3 },
    { day: 'Sun', level: 3 },
  ],
};

export const regionalAlerts = [
  {
    id: 'alert-1',
    risk: 'high',
    riskLabel: 'High Risk',
    distance: '5km away',
    date: 'May 15, 2024',
    pestName: 'Brown Planthopper (Kayumangging Hanip)',
    scientificName: 'Nilaparvata lugens',
    location: 'CABANATUAN CITY',
    description:
      "Mabilis ang pagdami ng hanip sa mga karatig-bukid. Inirerekomenda ang pagpapatuloy ng pinit o 'alternate wetting and drying' upang mapigilan ang paglago ng mga peste.",
  },
  {
    id: 'alert-2',
    risk: 'medium',
    riskLabel: 'Moderate Risk',
    distance: '12km away',
    date: 'May 14, 2024',
    pestName: 'Rice Bug (Atangya / Aksip)',
    scientificName: 'Leptocorisa oratorius',
    location: 'SAN JOSE CITY',
    description:
      "Naitala ang pagtaas ng pinsala sa mga palayan sa 'milky stage'. Gumamit ng biological controls o traps.",
  },
];

export const pestGuide = [
  {
    id: 'bph',
    category: 'Rice Pests',
    categoryFil: 'RICE PESTS',
    dangerLevel: 'High Danger',
    name: 'Brown Planthopper',
    nameFil: 'Kayumangging Hanip',
    scientificName: 'Nilaparvata lugens',
    summary:
      'Maliit na insektong sumisipsip ng katas ng palay. Kapag dumami, natutuyo at namumula ang buong bukid — tinatawag na "hopperburn".',
    description:
      'Ang Brown Planthopper (BPH) ay sumisipsip ng katas mula sa puno ng palay. Kapag marami na sila, unti-unting natutuyo ang halaman hanggang sa mamatay ito — tinatawag itong "hopperburn". Sa matinding pagsalakay, posibleng mawala ang buong ani sa apektadong bahagi ng bukid. Malapit din itong nauugnay sa mga sakit tulad ng Rice Yellowing Syndrome, dahil dala-dala nito ang mga virus na nagiging sanhi nito.',
    signs: [
      'Pagdilaw o paninilaw ng ibabang bahagi ng puno',
      'Mga bahaging kayumanggi o tuyo sa bukid (hopperburn)',
      'Malagkit na "honeydew" sa puno at dahon',
      'Itim na amag (sooty mold) na lumalabas sa malagkit na bahagi',
    ],
    prevention: [
      'Alisin ang mga damo sa bukid at paligid nito — tirahan ito ng BPH',
      'Iwasan ang labis na pestisidyo — napapatay din nito ang mga natural na kaaway ng peste',
      'Gumamit ng variety na matibay laban sa BPH kung meron (tanungin sa inyong agriculture office)',
      'Suriin araw-araw sa seedbed, o lingguhan sa bukid — yugyugin nang bahagya ang puno at tingnan kung may lumalagpak na peste',
      'Gumamit ng "light trap" (ilaw sa gabi) para masubaybayan kung dumarami na ang BPH sa paligid',
    ],
  },
  {
    id: 'stem-borer',
    category: 'Rice Pests',
    categoryFil: 'RICE PESTS',
    dangerLevel: 'High Danger',
    name: 'Rice Stem Borer',
    nameFil: 'Aksip o Atip',
    scientificName: 'Scirpophaga incertulas',
    summary:
      'Ang uod nito ay kumakain sa loob ng puno ng palay, na nagdudulot ng tuyong sentrong usbong ("deadheart") o walang laman na uhay ("white head").',
    description:
      'Ang Rice Stem Borer ay may uod na pumapasok sa loob ng puno ng palay at kumakain dito mula sa loob. Sa yugtong bata pa ang halaman (vegetative stage), namamatay at natutuyo ang gitnang usbong nito — tinatawag na "deadheart". Sa yugto naman ng pamumulaklak (reproductive stage), lumalabas ang uhay na puti at walang laman — tinatawag na "white head". Isa ito sa dalawang pangunahing peste na sinusubaybayan ng app na ito.',
    signs: [
      'Tuyo at namamatay na gitnang usbong (deadheart)',
      'Puti at walang laman na uhay (white head)',
      'Maliliit na butas sa puno kung saan pumapasok ang uod',
    ],
    prevention: [
      'Gumamit ng variety na matibay laban sa peste',
      'Sa seedbed, hanapin at alisin ang mga itlog ng gagamba bago pa man mag-transplant',
      'Itaas ang tubig sa bukid paminsan-minsan para malunod ang mga itlog na nakadikit sa ibabang bahagi ng puno',
      'Bago mag-transplant, putulin ang dulo ng dahon para maalis ang mga itlog na kasama',
      'Sabay-sabay magtanim sa isang lugar, at alisin ang tuod pagkatapos umani para maputol ang siklo ng peste',
      'Panatilihin ang mga natural na kaaway nito tulad ng gagamba, uod-mangangain, at ibang kapaki-pakinabang na insekto',
    ],
  },
  {
    id: 'rice-yellowing-syndrome',
    category: 'Diseases',
    categoryFil: 'DISEASES',
    dangerLevel: 'Critical Risk',
    name: 'Rice Yellowing Syndrome',
    nameFil: 'Paninilaw ng Palay',
    scientificName: 'RRSV + RGSV co-infection',
    summary:
      'Sakit na dala-dala ng Brown Planthopper. Nagdudulot ng pagdilaw, pagkulot ng dahon, at pagkaantala ng paglaki ng palay.',
    description:
      'Ang Rice Yellowing Syndrome ay sanhi ng dalawang virus (RRSV at RGSV) na dala-dala ng Brown Planthopper. Kapag magkasabay na nakahawa ang dalawang virus sa iisang halaman, nagiging kulubot at kulot ang mga dahon at naaantala ang paglaki ng palay. Namumula-dilaw ang kulay ng dahon, kaya minsan nalilito ito sa ibang sakit na tungro. Dahil ang BPH ang nagdadala nito, ang pagsugpo sa BPH ay siya ring pinakamabisang paraan para maiwasan ang sakit na ito.',
    signs: [
      'Pagdilaw-kahel ng mga dahon',
      'Kulot o kulubot na hugis ng dahon',
      'Paputol-putol o antala sa paglaki ng halaman',
    ],
    prevention: [
      'Sugpuin ang Brown Planthopper — ito ang nagdadala ng sakit na ito',
      'Alisin ang mga halamang inaanay o may sintomas kaagad para hindi kumalat',
      'Gumamit ng variety na matibay laban sa BPH at sa viruses na ito',
      'Regular na suriin ang bukid para maagapan ang pagkalat',
    ],
  },
  {
    id: 'hopperburn',
    category: 'Diseases',
    categoryFil: 'DISEASES',
    dangerLevel: 'Critical Risk',
    name: 'Hopperburn',
    nameFil: 'Hopperburn',
    scientificName: '',
    summary:
      'Kumpletong pagkatuyo ng palay dahil sa napakaraming Brown Planthopper na sumisipsip ng katas nito.',
    description:
      'Ang Hopperburn ay ang paglala ng pinsala ng Brown Planthopper — kapag sobrang dami na ng hanip sa isang puno, unti-unti itong natutuyo hanggang sa mamatay nang buo. Sa mataas na antas ng peste, posibleng mawala ang buong ani sa apektadong bahagi. Sa bukid, karaniwang lumalabas ito sa mga puno na malapit nang anihin kung may humigit-kumulang 400 hanggang 500 BPH na kumakapit sa bawat puno. Para matiyak na Hopperburn ang sanhi at hindi ibang peste, tingnan din kung may itim na amag (sooty mold) sa ibaba ng puno.',
    signs: [
      'Kumpletong pagkatuyo o pagkamatay ng buong puno',
      'Malawak na bahaging kayumanggi sa bukid, parang nasunog',
      'Kadalasang nakikita sa mga puno na malapit nang anihin',
    ],
    prevention: [
      'Suriin nang maaga at regular ang bilang ng BPH bago pa umabot sa mapanganib na dami',
      'Kumilos kaagad kapag umabot na sa mataas na antas ng peste ayon sa Economic Threshold Level',
      'Sundin ang mga hakbang sa pag-iwas laban sa Brown Planthopper para hindi na umabot sa ganitong antas',
    ],
  },
  {
    id: 'sooty-mold',
    category: 'Diseases',
    categoryFil: 'DISEASES',
    dangerLevel: 'Warning Limit',
    name: 'Sooty Mold',
    nameFil: 'Itim na Amag',
    scientificName: '',
    summary:
      'Itim, malagkit na amag na tumutubo sa "honeydew" na iniiwan ng Brown Planthopper sa puno ng palay.',
    description:
      'Ang Sooty Mold ay itim at pulbos-pulbos na fungus na tumutubo sa "honeydew" — ang matamis at malagkit na dumi na iniiwan ng Brown Planthopper habang sumisipsip ito ng katas. Bagama’t hindi direktang sanhi ng pagkasira ng puno, ito ay senyales na maraming BPH ang nakatira o dumadaan sa lugar na iyon.',
    signs: [
      'Itim, pulbos-pulbos na amag sa ibaba ng puno at dahon',
      'Malagkit na bahagi ng puno bago lumitaw ang amag',
    ],
    prevention: [
      'Sugpuin ang Brown Planthopper — ito ang pinagmumulan ng honeydew na pinagtutubuan ng amag',
      'Regular na suriin ang ibabang bahagi ng puno para maagapan ang pagdami ng BPH',
    ],
  },
  {
    id: 'dead-heart',
    category: 'Diseases',
    categoryFil: 'DISEASES',
    dangerLevel: 'Critical Risk',
    name: 'Dead Heart',
    nameFil: 'Tuyong Gitnang Usbong',
    scientificName: '',
    summary:
      'Tuyo at namamatay na gitnang usbong ng palay dahil sa uod ng Rice Stem Borer na kumakain dito mula sa loob ng puno.',
    description:
      'Ang Dead Heart ay nangyayari kapag ang uod ng Rice Stem Borer ay pumasok sa loob ng puno ng palay habang bata pa ang halaman (vegetative stage) at kumain sa gitnang usbong nito. Dahil dito, natutuyo at namamatay ang gitnang bahagi ng puno, kahit buhay pa ang ibang bahagi nito.',
    signs: [
      'Tuyo at kayumanggi na gitnang usbong habang luntian pa ang paligid',
      'Madaling mahila ang tuyong usbong palabas ng puno',
      'Maliliit na butas sa ibabang bahagi ng puno',
    ],
    prevention: [
      'Sa seedbed, hanapin at alisin ang mga itlog ng peste bago mag-transplant',
      'Itaas ang tubig sa bukid paminsan-minsan para malunod ang mga itlog',
      'Gumamit ng variety na matibay laban sa Rice Stem Borer',
    ],
  },
  {
    id: 'white-head',
    category: 'Diseases',
    categoryFil: 'DISEASES',
    dangerLevel: 'Critical Risk',
    name: 'White Head',
    nameFil: 'Puting Uhay',
    scientificName: '',
    summary:
      'Puti at walang laman na uhay dahil sa uod ng Rice Stem Borer na kumain sa loob ng puno noong yugto ng pamumulaklak.',
    description:
      'Ang White Head ay nangyayari sa yugto ng pamumulaklak (reproductive stage) kapag ang uod ng Rice Stem Borer ay kumain sa loob ng puno bago pa man mabuo ang uhay. Dahil dito, lumalabas ang uhay na puti o kulay-abo, walang laman, at hindi humihitim tulad ng normal na uhay na may laman.',
    signs: [
      'Puti o kulay-abong uhay na walang laman ng bigas',
      'Uhay na tuwid at hindi yumuyuko dahil walang bigas',
      'Kadalasang magkahiwalay lang ang apektadong uhay sa gitna ng malusog na uhay',
    ],
    prevention: [
      'Gumamit ng light trap para masubaybayan ang paglipad ng gamu-gamo ng peste',
      'Sabay-sabay magtanim sa isang lugar para maputol ang siklo ng peste',
      'Alisin at sunugin o ibaon ang tuod pagkatapos umani',
    ],
  },
  {
    id: 'stem-tillers-hole',
    category: 'Diseases',
    categoryFil: 'DISEASES',
    dangerLevel: 'Warning Limit',
    name: 'Stems and Tillers Hole',
    nameFil: 'Butas sa Puno at Sanga',
    scientificName: '',
    summary:
      'Maliliit na butas sa puno at sanga ng palay kung saan pumapasok at nananatili ang uod ng Rice Stem Borer.',
    description:
      'Ang mga butas sa puno at sanga ng palay ay nabubuo kapag pumapasok ang uod ng Rice Stem Borer para kumain at manirahan sa loob nito. Kapag sinuri, may makikitang dumi ng uod (fecal matter) sa loob ng mga apektadong bahagi. Ito ang unang senyales bago pa man lumitaw ang mas malalang sintomas tulad ng dead heart o white head.',
    signs: [
      'Maliliit na butas sa gilid ng puno o sanga',
      'Dumi ng uod (fecal matter) na nakikita sa loob o labas ng butas',
      'Manipis o mahinang bahagi ng puno malapit sa butas',
    ],
    prevention: [
      'Suriin ang puno at sanga para sa maagang senyales ng butas bago pa lumala',
      'Alisin at itapon ang mga apektadong tangkay kung kaunti pa lamang',
      'Gumamit ng variety na matibay laban sa Rice Stem Borer',
    ],
  },
  {
    id: 'bph-prevention',
    category: 'Prevention',
    categoryFil: 'PREVENTION',
    dangerLevel: 'Warning Limit',
    name: 'Pag-iwas sa Brown Planthopper',
    nameFil: 'Pag-iwas sa Kayumangging Hanip',
    scientificName: '',
    summary:
      'Mga simpleng hakbang para maagapan ang paglaganap ng Brown Planthopper bago pa man ito maging outbreak.',
    description:
      'Ang pagsugpo sa Brown Planthopper ay nagsisimula sa maagang pagbabantay at malinis na kapaligiran. Ang mga sumusunod ay mga hakbang na maaaring gawin ng magsasaka mismo, bago pa kailanganin ang kemikal na pestisidyo.',
    signs: [],
    prevention: [
      'Alisin ang mga damo sa bukid at paligid nito — tirahan ito ng BPH',
      'Iwasan ang labis na pestisidyo — napapatay din nito ang mga natural na kaaway ng peste',
      'Gumamit ng variety na matibay laban sa BPH kung meron (tanungin sa inyong agriculture office)',
      'Suriin araw-araw sa seedbed, o lingguhan sa bukid — yugyugin nang bahagya ang puno at tingnan kung may lumalagpak na peste',
      'Gumamit ng "light trap" (ilaw sa gabi) para masubaybayan kung dumarami na ang BPH sa paligid',
    ],
  },
  {
    id: 'stem-borer-prevention',
    category: 'Prevention',
    categoryFil: 'PREVENTION',
    dangerLevel: 'Warning Limit',
    name: 'Pag-iwas sa Rice Stem Borer',
    nameFil: 'Pag-iwas sa Aksip o Atip',
    scientificName: '',
    summary:
      'Mga hakbang sa seedbed, pagtatanim, at pag-aani para maputol ang siklo ng buhay ng Rice Stem Borer.',
    description:
      'Ang Rice Stem Borer ay maaaring maagapan sa iba’t ibang yugto ng pagtatanim — mula sa seedbed hanggang sa pag-aani. Ang mga sumusunod na hakbang ay tumutulong maputol ang kanyang siklo ng buhay bago pa ito dumami.',
    signs: [],
    prevention: [
      'Gumamit ng variety na matibay laban sa peste',
      'Sa seedbed, hanapin at alisin ang mga itlog ng gagamba bago pa man mag-transplant',
      'Itaas ang tubig sa bukid paminsan-minsan para malunod ang mga itlog na nakadikit sa ibabang bahagi ng puno',
      'Bago mag-transplant, putulin ang dulo ng dahon para maalis ang mga itlog na kasama',
      'Sabay-sabay magtanim sa isang lugar, at alisin ang tuod pagkatapos umani para maputol ang siklo ng peste',
      'Panatilihin ang mga natural na kaaway nito tulad ng gagamba, uod-mangangain, at ibang kapaki-pakinabang na insekto',
    ],
  },
];

// Economic Threshold Level (ETL) reference table — Table 2 from the thesis
// ("Economic Threshold Level (ETL) Numerical Values by Pest Species, Crop
// Stage, and Risk Classification"). Standards per PhilRice and the DA
// Regional Crop Protection Center (DA-RCPC). Risk level is determined by
// crossing the pest species with the active crop stage (Vegetative vs
// Reproductive) against these boundaries.
export const etlThresholds = {
  bph: {
    unit: 'hoppers/hill',
    metricLabel: 'Bilang ng Hanip',
    Vegetative: { low: 10, medium: 20 }, // <10 Low, 10-20 Medium, >20 High
    Reproductive: { low: 5, medium: 10 }, // <5 Low, 5-10 Medium, >10 High
  },
  'stem-borer': {
    unit: '% dead hearts',
    metricLabel: '% Dead Hearts',
    Vegetative: { low: 2, medium: 5 }, // <2% Low, 2-5% Medium, >5% High
    // Reproductive stage is measured as % white ears instead of dead hearts.
    Reproductive: { low: 5, medium: 10, unit: '% white ears', metricLabel: '% White Ears' },
  },
};

export function classifyRisk(pestId, cropStage, measurement) {
  const table = etlThresholds[pestId]?.[cropStage];
  if (!table) return 'low';
  if (measurement > table.medium) return 'high';
  if (measurement >= table.low) return 'medium';
  return 'low';
}

// Builds a 14-day daily risk forecast (the thesis's actual output shape:
// a per-day Low/Medium/High classification across the 2-week window, not a
// single flat value) by walking from a start risk toward a peak risk over
// the window, mirroring how the BiLSTM's time-lagged climate reasoning
// would show an outbreak building up rather than appearing instantly.
const RISK_ORDER = ['low', 'medium', 'high'];
const DAY_NAMES_FIL = ['Lun', 'Mar', 'Miy', 'Huw', 'Biy', 'Sab', 'Lin'];

function buildForecast(startRisk, peakRisk, peakDayIndex) {
  const startIdx = RISK_ORDER.indexOf(startRisk);
  const peakIdx = RISK_ORDER.indexOf(peakRisk);
  const today = new Date();

  return Array.from({ length: 14 }, (_, i) => {
    const date = new Date(today);
    date.setDate(today.getDate() + i);
    const progress = peakDayIndex === 0 ? 1 : Math.min(1, i / peakDayIndex);
    const levelIdx = Math.round(startIdx + (peakIdx - startIdx) * progress);
    return {
      date,
      dayFil: DAY_NAMES_FIL[date.getDay() === 0 ? 6 : date.getDay() - 1],
      dateLabel: date.getDate(),
      risk: RISK_ORDER[levelIdx],
    };
  });
}

// Simulated detection results standing in for the backend's /api/predict
// response (ResNet-50 + BiLSTM classification). Structured exactly like the
// real response should be: pest identity, crop stage, the measured field
// indicator on the day of scanning, and a 14-day daily risk forecast built
// from the time-lagged climate reasoning described in the thesis. Three
// scenarios are kept so every overall risk level's UI can be reached
// (?risk=low|medium|high on /scan/result, see ScanResult.jsx).
export const scanDetectionByRisk = {
  low: {
    pestId: 'bph',
    cropStage: 'Vegetative',
    cropStageFil: 'Vegetative (Tillering)',
    measurement: 6,
    confidence: 0.93,
    forecast: buildForecast('low', 'low', 13),
  },
  medium: {
    pestId: 'bph',
    cropStage: 'Vegetative',
    cropStageFil: 'Vegetative (Tillering)',
    measurement: 14,
    confidence: 0.89,
    forecast: buildForecast('low', 'medium', 6),
  },
  high: {
    pestId: 'stem-borer',
    cropStage: 'Reproductive',
    cropStageFil: 'Reproductive (Panicle)',
    measurement: 13,
    confidence: 0.91,
    forecast: buildForecast('medium', 'high', 9),
  },
};

export const scanDetection = scanDetectionByRisk.medium;

export const pestTypeOptions = [
  'Brown Planthopper (Kayumangging Hanip)',
  'Rice Stem Borer (Aksip o Atip)',
  'Rice Leaf Folder (Uod na Tagatupi ng Dahon)',
  'Rice Bug (Atangya)',
  'Iba pa / Hindi sigurado',
];

export const severityOptions = [
  { id: 'low', label: 'Mababa', color: 'var(--color-primary)' },
  { id: 'medium', label: 'Katamtaman', color: 'var(--color-accent-orange)' },
  { id: 'high', label: 'Mataas', color: 'var(--color-accent-red)' },
];
