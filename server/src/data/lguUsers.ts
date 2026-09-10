export interface LguUser {
  username: string;
  password: string;
  roleLevel: string;
  province: string;
  municipality: string;
}

export const lguUsers: LguUser[] = [
  {
    username: 'munoz_tech_01',
    password: 'PestWatch!Mu2026',
    roleLevel: 'LGU_Tech',
    province: 'Nueva Ecija',
    municipality: 'Science City of Muñoz',
  },
  {
    username: 'cabanatuan_tech',
    password: 'PestWatch!Cab2026',
    roleLevel: 'LGU_Tech',
    province: 'Nueva Ecija',
    municipality: 'Cabanatuan City',
  },
  {
    username: 'concepcion_tech',
    password: 'PestWatch!Con2026',
    roleLevel: 'LGU_Tech',
    province: 'Tarlac',
    municipality: 'Concepcion',
  },
  {
    username: 'sanmiguel_tech',
    password: 'PestWatch!SM2026',
    roleLevel: 'LGU_Tech',
    province: 'Bulacan',
    municipality: 'San Miguel',
  },
  {
    username: 'arayat_tech_01',
    password: 'PestWatch!Ara2026',
    roleLevel: 'LGU_Tech',
    province: 'Pampanga',
    municipality: 'Arayat',
  },
];
