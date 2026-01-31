/**
 * Fungsi untuk menangani proses login dan navigasi paksa ke halaman GetNum
 * @param {import('playwright').Page} page 
 * @param {string} email 
 * @param {string} password 
 * @param {string} loginUrl 
 */
async function performLogin(page, email, password, loginUrl) {
    console.log("[BROWSER] Membuka halaman login...");
    await page.goto(loginUrl, { waitUntil: 'networkidle', timeout: 60000 });
    
    // Tunggu input berdasarkan selector DevTools asli yang Anda berikan
    await page.waitForSelector("input[type='email']", { state: 'visible', timeout: 30000 });
    
    // Isi data login
    await page.fill("input[type='email']", email); 
    await page.fill("input[type='password']", password);
    
    console.log("[BROWSER] Menekan tombol Sign In...");
    const loginBtn = page.locator("button[type='submit']");
    await loginBtn.click();

    // 1. Tunggu sampai sistem melakukan redirect otomatis ke dashboard utama
    console.log("[BROWSER] Menunggu redirect dashboard...");
    await page.waitForURL('**/mdashboard', { timeout: 60000 });

    // 2. PAKSA NAVIGASI (Paste Ulang URL) ke halaman GetNum
    // Ini langkah krusial agar bot tidak tertahan di dashboard utama
    console.log("[BROWSER] Berhasil login. Memaksa navigasi ke halaman target: GetNum...");
    await page.goto("https://stexsms.com/mdashboard/getnum", { 
        waitUntil: 'networkidle', 
        timeout: 60000 
    });

    // Verifikasi apakah selector input range sudah ada untuk memastikan kita di halaman yang benar
    try {
        await page.waitForSelector("input[name='numberrange']", { timeout: 10000 });
        console.log("[BROWSER] Konfirmasi: Sudah berada di halaman GetNum.");
    } catch (e) {
        console.log("[BROWSER] Peringatan: Input range belum terlihat, mencoba refresh sekali lagi...");
        await page.reload({ waitUntil: 'networkidle' });
    }
}

module.exports = { performLogin };
