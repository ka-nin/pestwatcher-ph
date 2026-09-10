export interface LguUser {
  username: string;
  password: string;
  roleLevel: string;
  province: string;
  municipality: string;
  latitude: number;
  longitude: number;
}

export const lguUsers: LguUser[] = [
  {
    username: 'munoz_tech_01',
    password: 'PestWatch!Mu2026',
    roleLevel: 'LGU_Tech',
    province: 'Nueva Ecija',
    municipality: 'Science City of Muñoz',
    latitude: 15.7167,
    longitude: 120.9167,
  },
  {
    username: 'cabanatuan_tech',
    password: 'PestWatch!Cab2026',
    roleLevel: 'LGU_Tech',
    province: 'Nueva Ecija',
    municipality: 'Cabanatuan City',
    latitude: 15.4864,
    longitude: 120.9689,
  },
  {
    username: 'concepcion_tech',
    password: 'PestWatch!Con2026',
    roleLevel: 'LGU_Tech',
    province: 'Tarlac',
    municipality: 'Concepcion',
    latitude: 15.3167,
    longitude: 120.6333,
  },
  {
    username: 'sanmiguel_tech',
    password: 'PestWatch!SM2026',
    roleLevel: 'LGU_Tech',
    province: 'Bulacan',
    municipality: 'San Miguel',
    latitude: 15.15,
    longitude: 120.9667,
  },
  {
    username: 'arayat_tech_01',
    password: 'PestWatch!Ara2026',
    roleLevel: 'LGU_Tech',
    province: 'Pampanga',
    municipality: 'Arayat',
    latitude: 15.4167,
    longitude: 120.7333,
  },
];
