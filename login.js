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
    
    // Tunggu input berdasarkan selector DevTools asli
    await page.waitForSelector("input[type='email']", { state: 'visible', timeout: 30000 });
    
    // Isi data login
    await page.fill("input[type='email']", email); 
    await page.fill("input[type='password']", password);
    
    console.log("[BROWSER] Menekan tombol Sign In...");
    const loginBtn = page.locator("button[type='submit']");
    await loginBtn.click();

    // 1. TUNGGU URL DASHBOARD UTAMA
    // Kita menunggu sampai halaman mdashboard termuat sepenuhnya setelah login
    console.log("[BROWSER] Menunggu mdashboard dimuat...");
    try {
        await page.waitForURL('https://stexsms.com/mdashboard', { 
            waitUntil: 'networkidle', 
            timeout: 60000 
        });
        console.log("[BROWSER] Login Terdeteksi. Sekarang di halaman: /mdashboard");
    } catch (error) {
        console.log("[BROWSER] Peringatan: Menunggu URL mdashboard timeout, mencoba lanjut ke redirect...");
    }

    // 2. REDIRECT PAKSA KE GETNUM
    // Setelah terkonfirmasi di dashboard, baru kita "paste" URL target
    console.log("[BROWSER] Melakukan redirect ke halaman target: GetNum...");
    await page.goto("https://stexsms.com/mdashboard/getnum", { 
        waitUntil: 'networkidle', 
        timeout: 60000 
    });

    // Verifikasi akhir untuk memastikan input range muncul
    try {
        await page.waitForSelector("input[name='numberrange']", { state: 'visible', timeout: 15000 });
        console.log("[BROWSER] Sukses: Siap mengambil nomor di halaman GetNum.");
    } catch (e) {
        console.log("[BROWSER] Gagal memverifikasi elemen halaman GetNum, mencoba refresh...");
        await page.reload({ waitUntil: 'networkidle' });
    }
}

module.exports = { performLogin };
