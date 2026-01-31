/**
 * Fungsi untuk menangani proses login ke StexSMS menggunakan selector DevTools asli
 * @param {import('playwright').Page} page 
 * @param {string} email 
 * @param {string} password 
 * @param {string} loginUrl 
 */
async function performLogin(page, email, password, loginUrl) {
    console.log("[BROWSER] Logging in...");
    await page.goto(loginUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    
    // Tunggu input muncul agar tidak gagal (Selector disesuaikan dengan DevTools Anda)
    await page.waitForSelector("input[type='email']", { state: 'visible', timeout: 30000 });
    
    // Mengisi Email
    await page.fill("input[type='email']", email); 
    
    // Mengisi Password
    await page.fill("input[type='password']", password);
    
    // Klik tombol submit (Selector: button[type='submit'])
    const loginBtn = page.locator("button[type='submit']");
    
    if (await loginBtn.isVisible()) {
        await loginBtn.click();
    } else {
         // Fallback jika tombol tidak terdeteksi langsung
         await page.keyboard.press('Enter');
    }

    // Tunggu sampai redirect ke dashboard berhasil
    await page.waitForURL('**/mdashboard/**', { timeout: 60000 });
}

module.exports = { performLogin };
