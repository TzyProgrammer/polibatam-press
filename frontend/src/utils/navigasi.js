// Tujuan setelah login (?next=...) hanya boleh path di aplikasi ini, bukan URL situs lain.
export function tujuanAman(next, cadangan = '/') {
  if (typeof next !== 'string' || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) {
    return cadangan
  }
  return next
}
