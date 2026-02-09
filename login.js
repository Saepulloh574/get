/**
 * Fungsi untuk menangani proses login dan navigasi paksa ke halaman GetNum
 * Versi Puppeteer - Dioptimalkan untuk Termux
 * @param {import('puppeteer-core').Page} page 
 */
async function performLogin(page, email, password, loginUrl) {
    console.log("[BROWSER] Membuka halaman login...");
    // Puppeteer menggunakan networkidle2 untuk stabilitas navigasi
    await page.goto(loginUrl, { waitUntil: 'networkidle2', timeout: 60000 });
    
    console.log("[BROWSER] Menunggu stabilitas browser (2 detik)...");
    await new Promise(r => setTimeout(r, 2000));

    // Tunggu input muncul (Selector disesuaikan untuk Puppeteer)
    await page.waitForSelector("input[type='email']", { visible: true, timeout: 30000 });
    
    console.log("[BROWSER] Mengisi email dan password...");
    // Ganti .fill() menjadi .type()
    await page.type("input[type='email']", email, { delay: 50 }); 
    await page.type("input[type='password']", password, { delay: 50 });
    
    console.log("[BROWSER] Menekan tombol Sign In...");
    // Di Puppeteer, .click() bisa langsung menggunakan selector string
    await page.click("button[type='submit']");

    console.log("[BROWSER] Menunggu proses login selesai (3 detik)...");
    await new Promise(r => setTimeout(r, 3000));

    // PAKSA REDIRECT LANGSUNG KE GETNUM
    console.log("[BROWSER] Melakukan navigasi paksa ke: https://stexsms.com/mdashboard/getnum");
    await page.goto("https://stexsms.com/mdashboard/getnum", { 
        waitUntil: 'networkidle2', 
        timeout: 60000 
    });

    // Verifikasi apakah sudah di halaman yang benar
    try {
        await page.waitForSelector("input[name='numberrange']", { visible: true, timeout: 15000 });
        console.log("[BROWSER] KONFIRMASI: Berhasil berada di halaman GetNum.");
    } catch (e) {
        console.log("[BROWSER] Peringatan: Input range tidak ditemukan, mencoba refresh halaman...");
        await page.reload({ waitUntil: 'networkidle2' });
    }
}

module.exports = { performLogin };
