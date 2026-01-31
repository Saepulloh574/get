/**
 * Fungsi untuk menangani proses login dan navigasi paksa ke halaman GetNum
 * @param {import('playwright').Page} page 
 * @param {string} email 
 * @param {string} password 
 * @param {string} loginUrl 
 */
async function performLogin(page, email, password, loginUrl) {
    console.log("[BROWSER] Membuka halaman login...");
    await page.goto(loginUrl, { waitUntil: 'load', timeout: 60000 });
    
    // TUNGGU CHROMIUM TERBUKA SEMPURNA SELAMA 2 DETIK
    console.log("[BROWSER] Menunggu stabilitas browser (2 detik)...");
    await new Promise(r => setTimeout(r, 2000));

    // Tunggu input muncul berdasarkan selector DevTools asli
    await page.waitForSelector("input[type='email']", { state: 'visible', timeout: 30000 });
    
    console.log("[BROWSER] Mengisi email dan password...");
    // Menggunakan fill agar lebih cepat dan akurat
    await page.fill("input[type='email']", email); 
    await page.fill("input[type='password']", password);
    
    console.log("[BROWSER] Menekan tombol Sign In...");
    const loginBtn = page.locator("button[type='submit']");
    await loginBtn.click();

    // 1. TUNGGU SAMPAI MASUK KE DASHBOARD UTAMA
    console.log("[BROWSER] Menunggu redirect otomatis ke /mdashboard...");
    try {
        await page.waitForURL('https://stexsms.com/mdashboard', { 
            waitUntil: 'networkidle', 
            timeout: 60000 
        });
        console.log("[BROWSER] Login Berhasil. Sekarang berada di Dashboard.");
    } catch (error) {
        console.log("[BROWSER] Peringatan: Redirect otomatis lambat, mencoba paksa navigasi...");
    }

    // 2. PASTE ULANG URL TARGET KE GETNUM
    console.log("[BROWSER] Melakukan navigasi paksa ke: https://stexsms.com/mdashboard/getnum");
    await page.goto("https://stexsms.com/mdashboard/getnum", { 
        waitUntil: 'networkidle', 
        timeout: 60000 
    });

    // Verifikasi akhir apakah input range sudah muncul di halaman target
    try {
        await page.waitForSelector("input[name='numberrange']", { state: 'visible', timeout: 15000 });
        console.log("[BROWSER] KONFIRMASI: Berhasil berada di halaman GetNum. Siap bekerja!");
    } catch (e) {
        console.log("[BROWSER] Error: Halaman GetNum tidak termuat sempurna. Melakukan refresh...");
        await page.reload({ waitUntil: 'networkidle' });
    }
}

module.exports = { performLogin };
