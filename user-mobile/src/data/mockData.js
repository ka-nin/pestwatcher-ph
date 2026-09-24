// Mock data standing in for the FastAPI backend responses described in
// backend/README.md. Shapes here should match the real API contract so
// swapping in real fetch calls later is a drop-in replacement.

export const currentLocation = {
  province: 'Nueva Ecija',
  region: 'Central Luzon',
  latitude: 15.58,
  longitude: 120.95,
};

export const dashboardSummary = {
  riskLevel: 'low', // 'low' | 'medium' | 'high'
  riskLabelFil: 'Mababang Panganib',
  pestFil: 'Kayumangging Hanip at Aksip',
  pestEn: 'Brown Planthopper and Stem Borer',
  message:
    'Mababa ang posibilidad ng pagtaas ng peste sa loob ng dalawang linggo. Ipagpatuloy ang normal na pagmamanman. Hindi kinakailangan ang agarang pag-ispray ng pestisidyo.',
  tip: 'I-check ang dahon, puno, at dami ng peste bago mag-apply ng anumang kemikal.',
  tipEn: 'Check the leaves, stems, and pest count before applying any chemical.',
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
    summaryEn:
      'A tiny insect that sucks sap from rice plants. When numbers build up, the whole field dries out and turns brown — called "hopperburn".',
    description:
      'Ang Brown Planthopper (BPH) ay sumisipsip ng katas mula sa puno ng palay. Kapag marami na sila, unti-unting natutuyo ang halaman hanggang sa mamatay ito — tinatawag itong "hopperburn". Sa matinding pagsalakay, posibleng mawala ang buong ani sa apektadong bahagi ng bukid. Malapit din itong nauugnay sa mga sakit tulad ng Rice Yellowing Syndrome, dahil dala-dala nito ang mga virus na nagiging sanhi nito.',
    descriptionEn:
      'The Brown Planthopper (BPH) feeds by sucking sap from the base of the rice stem. As their numbers grow, the plant gradually dries out until it dies — a condition called "hopperburn." In severe infestations, the entire yield in the affected part of the field can be lost. BPH is also closely linked to diseases such as Rice Yellowing Syndrome, since it carries the viruses that cause it.',
    signs: [
      'Pagdilaw o paninilaw ng ibabang bahagi ng puno',
      'Mga bahaging kayumanggi o tuyo sa bukid (hopperburn)',
      'Malagkit na "honeydew" sa puno at dahon',
      'Itim na amag (sooty mold) na lumalabas sa malagkit na bahagi',
    ],
    signsEn: [
      'Yellowing of the lower part of the plant',
      'Brown, dried-out patches in the field (hopperburn)',
      'Sticky "honeydew" on the stems and leaves',
      'Black sooty mold growing on the sticky residue',
    ],
    prevention: [
      'Alisin ang mga damo sa bukid at paligid nito — tirahan ito ng BPH',
      'Iwasan ang labis na pestisidyo — napapatay din nito ang mga natural na kaaway ng peste',
      'Gumamit ng variety na matibay laban sa BPH kung meron (tanungin sa inyong agriculture office)',
      'Suriin araw-araw sa seedbed, o lingguhan sa bukid — yugyugin nang bahagya ang puno at tingnan kung may lumalagpak na peste',
      'Gumamit ng "light trap" (ilaw sa gabi) para masubaybayan kung dumarami na ang BPH sa paligid',
    ],
    preventionEn: [
      'Remove weeds in and around the field — they shelter BPH',
      "Avoid excessive pesticide use — it also kills the pest's natural enemies",
      'Use a BPH-resistant variety if available (ask your local agriculture office)',
      'Check the seedbed daily, or weekly in the field — gently shake the plant and look for pests falling off',
      'Use a light trap at night to monitor rising BPH numbers nearby',
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
    summaryEn:
      'Its larva feeds inside the rice stem, causing a dried-out central shoot ("deadheart") or an empty, unfilled panicle ("white head").',
    description:
      'Ang Rice Stem Borer ay may uod na pumapasok sa loob ng puno ng palay at kumakain dito mula sa loob. Sa yugtong bata pa ang halaman (vegetative stage), namamatay at natutuyo ang gitnang usbong nito — tinatawag na "deadheart". Sa yugto naman ng pamumulaklak (reproductive stage), lumalabas ang uhay na puti at walang laman — tinatawag na "white head". Isa ito sa dalawang pangunahing peste na sinusubaybayan ng app na ito.',
    descriptionEn:
      'The Rice Stem Borer’s larva bores into the rice stem and feeds from the inside. During the plant’s early growth (vegetative stage), the central shoot dies and dries out — called "deadheart." During the flowering stage (reproductive stage), the resulting panicle emerges white and empty — called "white head." This is one of the two primary pests this app tracks.',
    signs: [
      'Tuyo at namamatay na gitnang usbong (deadheart)',
      'Puti at walang laman na uhay (white head)',
      'Maliliit na butas sa puno kung saan pumapasok ang uod',
    ],
    signsEn: [
      'Dried, dying central shoot (deadheart)',
      'White, empty panicle (white head)',
      'Small holes in the stem where the larva entered',
    ],
    prevention: [
      'Gumamit ng variety na matibay laban sa peste',
      'Sa seedbed, hanapin at alisin ang mga itlog ng gagamba bago pa man mag-transplant',
      'Itaas ang tubig sa bukid paminsan-minsan para malunod ang mga itlog na nakadikit sa ibabang bahagi ng puno',
      'Bago mag-transplant, putulin ang dulo ng dahon para maalis ang mga itlog na kasama',
      'Sabay-sabay magtanim sa isang lugar, at alisin ang tuod pagkatapos umani para maputol ang siklo ng peste',
      'Panatilihin ang mga natural na kaaway nito tulad ng gagamba, uod-mangangain, at ibang kapaki-pakinabang na insekto',
    ],
    preventionEn: [
      'Use a pest-resistant variety',
      "In the seedbed, look for and remove the pest's egg masses before transplanting",
      'Periodically raise the water level in the field to drown egg masses stuck to the lower part of the stem',
      'Before transplanting, trim the leaf tips to remove any egg masses on them',
      "Plant in the same area at the same time, and remove stubble after harvest to break the pest's life cycle",
      'Preserve natural enemies such as spiders, predatory caterpillars, and other beneficial insects',
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
    summaryEn:
      'A disease carried by the Brown Planthopper. Causes yellowing, leaf curling, and stunted rice growth.',
    description:
      'Ang Rice Yellowing Syndrome ay sanhi ng dalawang virus (RRSV at RGSV) na dala-dala ng Brown Planthopper. Kapag magkasabay na nakahawa ang dalawang virus sa iisang halaman, nagiging kulubot at kulot ang mga dahon at naaantala ang paglaki ng palay. Namumula-dilaw ang kulay ng dahon, kaya minsan nalilito ito sa ibang sakit na tungro. Dahil ang BPH ang nagdadala nito, ang pagsugpo sa BPH ay siya ring pinakamabisang paraan para maiwasan ang sakit na ito.',
    descriptionEn:
      'Rice Yellowing Syndrome is caused by two viruses (RRSV and RGSV) carried by the Brown Planthopper. When a single plant is co-infected with both viruses, its leaves become wrinkled and curled, and its growth is stunted. The leaves turn a yellow-orange color, which is sometimes confused with tungro disease. Since BPH is the carrier, controlling BPH is also the most effective way to prevent this disease.',
    signs: [
      'Pagdilaw-kahel ng mga dahon',
      'Kulot o kulubot na hugis ng dahon',
      'Paputol-putol o antala sa paglaki ng halaman',
    ],
    signsEn: [
      'Yellow-orange discoloration of the leaves',
      'Curled or wrinkled leaf shape',
      'Stunted or interrupted plant growth',
    ],
    prevention: [
      'Sugpuin ang Brown Planthopper — ito ang nagdadala ng sakit na ito',
      'Alisin ang mga halamang inaanay o may sintomas kaagad para hindi kumalat',
      'Gumamit ng variety na matibay laban sa BPH at sa viruses na ito',
      'Regular na suriin ang bukid para maagapan ang pagkalat',
    ],
    preventionEn: [
      'Control the Brown Planthopper — it carries this disease',
      'Remove infested or symptomatic plants right away to stop it from spreading',
      'Use a variety resistant to both BPH and these viruses',
      'Inspect the field regularly to catch spread early',
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
    summaryEn:
      'Complete drying-out of the rice plant caused by an overwhelming number of Brown Planthoppers feeding on its sap.',
    description:
      'Ang Hopperburn ay ang paglala ng pinsala ng Brown Planthopper — kapag sobrang dami na ng hanip sa isang puno, unti-unti itong natutuyo hanggang sa mamatay nang buo. Sa mataas na antas ng peste, posibleng mawala ang buong ani sa apektadong bahagi. Sa bukid, karaniwang lumalabas ito sa mga puno na malapit nang anihin kung may humigit-kumulang 400 hanggang 500 BPH na kumakapit sa bawat puno. Para matiyak na Hopperburn ang sanhi at hindi ibang peste, tingnan din kung may itim na amag (sooty mold) sa ibaba ng puno.',
    descriptionEn:
      'Hopperburn is the advanced stage of Brown Planthopper damage — when a plant is carrying far too many hoppers, it gradually dries out until it dies completely. At high pest densities, the entire yield in the affected area can be lost. In the field, it typically appears in plants nearing harvest once roughly 400 to 500 BPH are clustered on a single stem. To confirm Hopperburn rather than another cause, also check for black sooty mold at the base of the plant.',
    signs: [
      'Kumpletong pagkatuyo o pagkamatay ng buong puno',
      'Malawak na bahaging kayumanggi sa bukid, parang nasunog',
      'Kadalasang nakikita sa mga puno na malapit nang anihin',
    ],
    signsEn: [
      'Complete drying or death of the whole plant',
      'Large scorched-looking brown patches across the field',
      'Most often seen in plants nearing harvest',
    ],
    prevention: [
      'Suriin nang maaga at regular ang bilang ng BPH bago pa umabot sa mapanganib na dami',
      'Kumilos kaagad kapag umabot na sa mataas na antas ng peste ayon sa Economic Threshold Level',
      'Sundin ang mga hakbang sa pag-iwas laban sa Brown Planthopper para hindi na umabot sa ganitong antas',
    ],
    preventionEn: [
      'Monitor BPH numbers early and regularly, before they reach dangerous levels',
      'Act immediately once pest levels reach the Economic Threshold Level',
      "Follow Brown Planthopper prevention measures so it never reaches this stage",
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
    summaryEn:
      'A black, sticky mold that grows on the "honeydew" left behind by the Brown Planthopper on rice plants.',
    description:
      'Ang Sooty Mold ay itim at pulbos-pulbos na fungus na tumutubo sa "honeydew" — ang matamis at malagkit na dumi na iniiwan ng Brown Planthopper habang sumisipsip ito ng katas. Bagama’t hindi direktang sanhi ng pagkasira ng puno, ito ay senyales na maraming BPH ang nakatira o dumadaan sa lugar na iyon.',
    descriptionEn:
      'Sooty Mold is a black, powdery fungus that grows on "honeydew" — the sweet, sticky residue the Brown Planthopper leaves behind while feeding on sap. While it doesn’t directly damage the plant, it’s a sign that a large number of BPH are living in or passing through the area.',
    signs: [
      'Itim, pulbos-pulbos na amag sa ibaba ng puno at dahon',
      'Malagkit na bahagi ng puno bago lumitaw ang amag',
    ],
    signsEn: [
      'Black, powdery mold on the lower stem and leaves',
      'Sticky residue on the stem before the mold appears',
    ],
    prevention: [
      'Sugpuin ang Brown Planthopper — ito ang pinagmumulan ng honeydew na pinagtutubuan ng amag',
      'Regular na suriin ang ibabang bahagi ng puno para maagapan ang pagdami ng BPH',
    ],
    preventionEn: [
      'Control the Brown Planthopper — it produces the honeydew the mold grows on',
      'Regularly inspect the lower part of the plant to catch rising BPH numbers early',
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
    summaryEn:
      "A dried, dying central shoot in rice caused by the Rice Stem Borer's larva feeding inside the stem.",
    description:
      'Ang Dead Heart ay nangyayari kapag ang uod ng Rice Stem Borer ay pumasok sa loob ng puno ng palay habang bata pa ang halaman (vegetative stage) at kumain sa gitnang usbong nito. Dahil dito, natutuyo at namamatay ang gitnang bahagi ng puno, kahit buhay pa ang ibang bahagi nito.',
    descriptionEn:
      "Dead Heart occurs when the Rice Stem Borer's larva bores into the rice stem while the plant is still young (vegetative stage) and feeds on its central shoot. As a result, the center of the plant dries out and dies while the rest of it stays alive.",
    signs: [
      'Tuyo at kayumanggi na gitnang usbong habang luntian pa ang paligid',
      'Madaling mahila ang tuyong usbong palabas ng puno',
      'Maliliit na butas sa ibabang bahagi ng puno',
    ],
    signsEn: [
      'Dried, brown central shoot while the surrounding tissue is still green',
      'The dried shoot pulls out easily from the stem',
      'Small holes in the lower part of the stem',
    ],
    prevention: [
      'Sa seedbed, hanapin at alisin ang mga itlog ng peste bago mag-transplant',
      'Itaas ang tubig sa bukid paminsan-minsan para malunod ang mga itlog',
      'Gumamit ng variety na matibay laban sa Rice Stem Borer',
    ],
    preventionEn: [
      "In the seedbed, find and remove the pest's egg masses before transplanting",
      'Periodically raise the water level in the field to drown the egg masses',
      'Use a variety resistant to the Rice Stem Borer',
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
    summaryEn:
      "A white, empty panicle caused by the Rice Stem Borer's larva feeding inside the stem during the flowering stage.",
    description:
      'Ang White Head ay nangyayari sa yugto ng pamumulaklak (reproductive stage) kapag ang uod ng Rice Stem Borer ay kumain sa loob ng puno bago pa man mabuo ang uhay. Dahil dito, lumalabas ang uhay na puti o kulay-abo, walang laman, at hindi humihitim tulad ng normal na uhay na may laman.',
    descriptionEn:
      "White Head occurs during the flowering stage (reproductive stage) when the Rice Stem Borer's larva feeds inside the stem before the panicle can fully form. As a result, the resulting panicle emerges white or gray, empty, and doesn't turn golden the way a normal, filled panicle does.",
    signs: [
      'Puti o kulay-abong uhay na walang laman ng bigas',
      'Uhay na tuwid at hindi yumuyuko dahil walang bigas',
      'Kadalasang magkahiwalay lang ang apektadong uhay sa gitna ng malusog na uhay',
    ],
    signsEn: [
      'White or gray panicle with no grain fill',
      "Panicle stands upright instead of drooping, since there's no grain weight",
      'Affected panicles usually appear scattered among otherwise healthy ones',
    ],
    prevention: [
      'Gumamit ng light trap para masubaybayan ang paglipad ng gamu-gamo ng peste',
      'Sabay-sabay magtanim sa isang lugar para maputol ang siklo ng peste',
      'Alisin at sunugin o ibaon ang tuod pagkatapos umani',
    ],
    preventionEn: [
      "Use a light trap to monitor the pest moth's flight activity",
      "Plant in the same area at the same time to break the pest's life cycle",
      'Remove and burn or bury stubble after harvest',
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
    summaryEn:
      "Small holes in the rice stem and tillers where the Rice Stem Borer's larva enters and lives.",
    description:
      "Ang mga butas sa puno at sanga ng palay ay nabubuo kapag pumapasok ang uod ng Rice Stem Borer para kumain at manirahan sa loob nito. Kapag sinuri, may makikitang dumi ng uod (fecal matter) sa loob ng mga apektadong bahagi. Ito ang unang senyales bago pa man lumitaw ang mas malalang sintomas tulad ng dead heart o white head.",
    descriptionEn:
      "Holes in the stem and tillers form when the Rice Stem Borer's larva bores in to feed and live inside. On inspection, larval frass (fecal matter) is visible inside the affected sections. This is the earliest sign, appearing before more serious symptoms like dead heart or white head develop.",
    signs: [
      'Maliliit na butas sa gilid ng puno o sanga',
      'Dumi ng uod (fecal matter) na nakikita sa loob o labas ng butas',
      'Manipis o mahinang bahagi ng puno malapit sa butas',
    ],
    signsEn: [
      'Small holes along the side of the stem or tiller',
      'Larval frass visible in or around the hole',
      'Thin or weakened stem tissue near the hole',
    ],
    prevention: [
      'Suriin ang puno at sanga para sa maagang senyales ng butas bago pa lumala',
      'Alisin at itapon ang mga apektadong tangkay kung kaunti pa lamang',
      'Gumamit ng variety na matibay laban sa Rice Stem Borer',
    ],
    preventionEn: [
      'Inspect stems and tillers for early signs of boring before it worsens',
      'Remove and dispose of affected tillers while numbers are still low',
      'Use a variety resistant to the Rice Stem Borer',
    ],
  },
  {
    id: 'bph-prevention',
    category: 'Prevention',
    categoryFil: 'PREVENTION',
    dangerLevel: 'Warning Limit',
    name: 'Pag-iwas sa Brown Planthopper',
    nameEn: 'Preventing Brown Planthopper',
    nameFil: 'Pag-iwas sa Kayumangging Hanip',
    scientificName: '',
    summary:
      'Mga simpleng hakbang para maagapan ang paglaganap ng Brown Planthopper bago pa man ito maging outbreak.',
    summaryEn:
      'Simple steps to catch a rising Brown Planthopper population before it becomes an outbreak.',
    description:
      'Ang pagsugpo sa Brown Planthopper ay nagsisimula sa maagang pagbabantay at malinis na kapaligiran. Ang mga sumusunod ay mga hakbang na maaaring gawin ng magsasaka mismo, bago pa kailanganin ang kemikal na pestisidyo.',
    descriptionEn:
      'Controlling the Brown Planthopper starts with early monitoring and a clean field environment. The following are steps a farmer can take on their own, before chemical pesticides become necessary.',
    signs: [],
    signsEn: [],
    prevention: [
      'Alisin ang mga damo sa bukid at paligid nito — tirahan ito ng BPH',
      'Iwasan ang labis na pestisidyo — napapatay din nito ang mga natural na kaaway ng peste',
      'Gumamit ng variety na matibay laban sa BPH kung meron (tanungin sa inyong agriculture office)',
      'Suriin araw-araw sa seedbed, o lingguhan sa bukid — yugyugin nang bahagya ang puno at tingnan kung may lumalagpak na peste',
      'Gumamit ng "light trap" (ilaw sa gabi) para masubaybayan kung dumarami na ang BPH sa paligid',
    ],
    preventionEn: [
      'Remove weeds in and around the field — they shelter BPH',
      "Avoid excessive pesticide use — it also kills the pest's natural enemies",
      'Use a BPH-resistant variety if available (ask your local agriculture office)',
      'Check the seedbed daily, or weekly in the field — gently shake the plant and look for pests falling off',
      'Use a light trap at night to monitor rising BPH numbers nearby',
    ],
  },
  {
    id: 'stem-borer-prevention',
    category: 'Prevention',
    categoryFil: 'PREVENTION',
    dangerLevel: 'Warning Limit',
    name: 'Pag-iwas sa Rice Stem Borer',
    nameEn: 'Preventing Rice Stem Borer',
    nameFil: 'Pag-iwas sa Aksip o Atip',
    scientificName: '',
    summary:
      'Mga hakbang sa seedbed, pagtatanim, at pag-aani para maputol ang siklo ng buhay ng Rice Stem Borer.',
    summaryEn:
      "Steps across the seedbed, planting, and harvest stages to break the Rice Stem Borer's life cycle.",
    description:
      'Ang Rice Stem Borer ay maaaring maagapan sa iba’t ibang yugto ng pagtatanim — mula sa seedbed hanggang sa pag-aani. Ang mga sumusunod na hakbang ay tumutulong maputol ang kanyang siklo ng buhay bago pa ito dumami.',
    descriptionEn:
      'The Rice Stem Borer can be intercepted at different stages of rice cultivation — from the seedbed through to harvest. The following steps help break its life cycle before its numbers grow.',
    signs: [],
    signsEn: [],
    prevention: [
      'Gumamit ng variety na matibay laban sa peste',
      'Sa seedbed, hanapin at alisin ang mga itlog ng gagamba bago pa man mag-transplant',
      'Itaas ang tubig sa bukid paminsan-minsan para malunod ang mga itlog na nakadikit sa ibabang bahagi ng puno',
      'Bago mag-transplant, putulin ang dulo ng dahon para maalis ang mga itlog na kasama',
      'Sabay-sabay magtanim sa isang lugar, at alisin ang tuod pagkatapos umani para maputol ang siklo ng peste',
      'Panatilihin ang mga natural na kaaway nito tulad ng gagamba, uod-mangangain, at ibang kapaki-pakinabang na insekto',
    ],
    preventionEn: [
      'Use a pest-resistant variety',
      "In the seedbed, look for and remove the pest's egg masses before transplanting",
      'Periodically raise the water level in the field to drown egg masses stuck to the lower part of the stem',
      'Before transplanting, trim the leaf tips to remove any egg masses on them',
      "Plant in the same area at the same time, and remove stubble after harvest to break the pest's life cycle",
      'Preserve natural enemies such as spiders, predatory caterpillars, and other beneficial insects',
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

// Limited to what the BiLSTM forecast model actually covers (BPH, RSB —
// see server-python/ml/config.py PEST_PARAMS). Anything else a farmer
// spots still gets logged, just bucketed as "Others" — it won't match a
// pest code in app/decision/report_anchor.py, so it can be reviewed by an
// LGU tech but never nudges a forecast.
// `value` is what's actually submitted to the backend (matched by keyword
// in server-python/app/decision/pest_matching.py) — kept exactly as before
// so switching the displayed label doesn't change what gets sent.
export const pestTypeOptions = [
  { value: 'Brown Planthopper (Kayumangging Hanip)', fil: 'Brown Planthopper (Kayumangging Hanip)', en: 'Brown Planthopper' },
  { value: 'Rice Stem Borer (Aksip o Atip)', fil: 'Rice Stem Borer (Aksip o Atip)', en: 'Rice Stem Borer' },
  { value: 'Others / Hindi Sigurado', fil: 'Others / Hindi Sigurado', en: 'Others / Not Sure' },
];

export const severityOptions = [
  { id: 'low', fil: 'Mababa', en: 'Low', color: 'var(--color-primary)' },
  { id: 'medium', fil: 'Katamtaman', en: 'Medium', color: 'var(--color-accent-orange)' },
  { id: 'high', fil: 'Mataas', en: 'High', color: 'var(--color-accent-red)' },
];

// Must match server-python/ml/config.py GROWTH_STAGE_BUCKETS exactly —
// these are the only six values the BiLSTM/ETL pipeline understands.
export const growthStageOptions = [
  'Seedling',
  'Tillering',
  'Elongation',
  'Panicle',
  'Flowering',
  'Ripening',
];
