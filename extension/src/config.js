// Single source of truth for environment + endpoints.
// Publishable key is safe in client; RLS policies on plonker_* tables gate access.
export const SUPABASE_URL = 'https://qhudavmfhbumknqddgig.supabase.co';
export const SUPABASE_KEY = 'sb_publishable_aGh_bbXqckmx-0DgaEySWg_9yyc_994';

export const DEFAULTS = {
  lives: 3,
  mcOptions: 4,
  noSpoilers: false,
  postRoundEnabled: true
};
