const fs = require('fs');
const path = require('path');
const axios = require('axios');
const cron = require('node-cron');
const dotenv = require('dotenv');
const { fork } = require('child_process');
const { Mutex } = require('async-mutex');

// --- STATE MANAGEMENT ---
const { state } = require('./helpers/state');

// --- IMPORT SHARED BROWSER (Sekarang menggunakan Puppeteer) ---
const { initSharedBrowser, getNewPage, restartBrowser } = require('./browser-shared.js');

// Load Env
dotenv.config();

// Load Configs
const HEADLESS_CONFIG = require('./headless.js');
const GLOBAL_COUNTRY_EMOJI = require('./country.json');

// --- KONFIGURASI DAN VARIABEL GLOBAL ---
const BOT_TOKEN = process.env.BOT_TOKEN;
const API = `https://api.telegram.org/bot${BOT_TOKEN}`;
const GROUP_ID_1 = parseInt(process.env.GROUP_ID_1);
const GROUP_ID_2 = parseInt(process.env.GROUP_ID_2);
const ADMIN_ID = parseInt(process.env.ADMIN_ID);
const STEX_EMAIL = process.env.STEX_EMAIL;
const STEX_PASSWORD = process.env.STEX_PASSWORD;

if (!BOT_TOKEN || !GROUP_ID_1 || !GROUP_ID_2 || !ADMIN_ID || !STEX_EMAIL || !STEX_PASSWORD) {
    console.error("[FATAL] Variabel lingkungan .env belum lengkap.");
    process.exit(1);
}

const TARGET_URL = "https://stexsms.com/mdashboard/getnum"; 
const BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot";
const GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1";
const GROUP_LINK_2 = "https://t.me/zura14g";

const OTP_PRICE = 0.003500;
const MIN_WD_AMOUNT = 1.000000;

// Files
const USER_FILE = "user.json";
const CACHE_FILE = "cache.json";
const INLINE_RANGE_FILE = "inline.json";
const WAIT_FILE = "wait.json";
const AKSES_GET10_FILE = "aksesget10.json";
const PROFILE_FILE = "profile.json";

// --- STATE ANTRIAN REAL FIFO & STANDBY PAGE ---
const queueMutex = new Mutex();
let userQueue = []; 
let processingUsers = new Set(); 
let mainStandbyPage = null; 

// Global State Sets/Maps
let waitingBroadcastInput = new Set();
let broadcastMessage = {};
let verifiedUsers = new Set();
let waitingAdminInput = new Set();
let manualRangeInput = new Set();
let get10RangeInput = new Set();
let waitingDanaInput = new Set();
let pendingMessage = {};
let lastUsedRange = {};

// Progress Bar Config
const MAX_BAR_LENGTH = 12;
const FILLED_CHAR = "█";
const EMPTY_CHAR = "░";

const STATUS_MAP = {
    0: "Menunggu antrian active..", 
    1: "Mempersiapkan tab standby..",
    3: "Mengirim permintaan nomor baru..",
    4: "Memulai pencarian di tabel data..",
    5: "Mencari nomor pada siklus satu run",
    8: "Mencoba ulang pada siklus dua wait",
    12: "Nomor ditemukan memproses data fin"
};

// ==============================================================================
// FUNGSI UTILITAS MANAJEMEN FILE
// ==============================================================================

function loadJson(filename, defaultVal = []) {
    if (fs.existsSync(filename)) {
        try { return JSON.parse(fs.readFileSync(filename, 'utf8')); } catch (e) { return defaultVal; }
    }
    return defaultVal;
}
function saveJson(filename, data) { fs.writeFileSync(filename, JSON.stringify(data, null, 2)); }
function loadUsers() { return new Set(loadJson(USER_FILE, [])); }
function saveUsers(userId) {
    const users = loadUsers();
    if (!users.has(userId)) { users.add(userId); saveJson(USER_FILE, Array.from(users)); }
}
function loadCache() { return loadJson(CACHE_FILE, []); }
function saveCache(entry) {
    const cache = loadCache();
    if (cache.length >= 1000) cache.shift();
    cache.push(entry);
    saveJson(CACHE_FILE, cache);
}
function normalizeNumber(number) {
    let norm = String(number).trim().replace(/[\s-]/g, "");
    if (!norm.startsWith('+') && /^\d+$/.test(norm)) norm = '+' + norm;
    return norm;
}
function isInCache(number) {
    const cache = loadCache();
    const norm = normalizeNumber(number);
    return cache.some(entry => normalizeNumber(entry.number) === norm);
}
function loadInlineRanges() { return loadJson(INLINE_RANGE_FILE, []); }
function saveInlineRanges(ranges) { saveJson(INLINE_RANGE_FILE, ranges); }
function loadAksesGet10() { return new Set(loadJson(AKSES_GET10_FILE, [])); }
function saveAksesGet10(userId) {
    const akses = loadAksesGet10();
    akses.add(parseInt(userId));
    saveJson(AKSES_GET10_FILE, Array.from(akses));
}
function hasGet10Access(userId) {
    if (userId === ADMIN_ID) return true;
    return loadAksesGet10().has(parseInt(userId));
}
function loadProfiles() { return loadJson(PROFILE_FILE, {}); }
function saveProfiles(data) { saveJson(PROFILE_FILE, data); }

function getUserProfile(userId, firstName = "User") {
    const profiles = loadProfiles();
    const strId = String(userId);
    const today = new Date().toISOString().split('T')[0];
    if (!profiles[strId]) {
        profiles[strId] = { 
            name: firstName, 
            dana: "Belum Diset", 
            dana_an: "Belum Diset", 
            balance: 0.000000, 
            otp_semua: 0, 
            otp_hari_ini: 0, 
            last_active: today,
            last_msg_id: null 
        };
        saveProfiles(profiles);
    } else {
        if (profiles[strId].name !== firstName) { profiles[strId].name = firstName; saveProfiles(profiles); }
        if (profiles[strId].last_active !== today) { profiles[strId].otp_hari_ini = 0; profiles[strId].last_active = today; saveProfiles(profiles); }
    }
    return profiles[strId];
}

function updateUserDana(userId, danaNumber, danaName) {
    const profiles = loadProfiles();
    if (profiles[String(userId)]) {
        profiles[String(userId)].dana = danaNumber;
        profiles[String(userId)].dana_an = danaName;
        saveProfiles(profiles); return true;
    } return false;
}
function loadWaitList() { return loadJson(WAIT_FILE, []); }
function saveWaitList(data) { saveJson(WAIT_FILE, data); }
function addToWaitList(number, userId, username, firstName) {
    let waitList = loadWaitList();
    const norm = normalizeNumber(number);
    let identity = username ? `@${username.replace('@', '')}` : `<a href="tg://user?id=${userId}">${firstName}</a>`;
    waitList = waitList.filter(item => item.number !== norm);
    waitList.push({ number: norm, user_id: userId, username: identity, timestamp: Date.now() / 1000 });
    saveWaitList(waitList);
}
function getProgressMessage(currentStep, totalSteps, prefixRange, numCount) {
    const progressRatio = Math.min(currentStep / 12, 1.0);
    const filledCount = Math.ceil(progressRatio * MAX_BAR_LENGTH);
    const emptyCount = MAX_BAR_LENGTH - filledCount;
    const bar = FILLED_CHAR.repeat(filledCount) + EMPTY_CHAR.repeat(emptyCount);
    let status = STATUS_MAP[currentStep] || STATUS_MAP[0];
    return `<code>${status}</code>\n<blockquote>Range: <code>${prefixRange}</code> | Jumlah: <code>${numCount}</code></blockquote>\n<code>Load:</code> [${bar}]`;
}
function generateInlineKeyboard(ranges) {
    const keyboard = [];
    ranges.forEach(item => {
        const service = item.service || "WA";
        const text = `${item.emoji} ${item.country} ${service}`;
        const callbackData = `select_range:${item.range}`;
        keyboard.push([{ text: text, callback_data: callbackData }]);
    });
    keyboard.push([{ text: "INPUT MANUAL RANGE..🖊️", callback_data: "manual_range" }]);
    return { inline_keyboard: keyboard };
}

// ==============================================================================
// FUNGSI API TELEGRAM
// ==============================================================================

async function tgDelete(chatId, messageId) {
    try { await axios.post(`${API}/deleteMessage`, { chat_id: chatId, message_id: messageId }); } catch (e) { }
}

async function tgSend(chatId, text, replyMarkup = null) {
    const strId = String(chatId);
    const profiles = loadProfiles();
    if (profiles[strId] && profiles[strId].last_msg_id) {
        await tgDelete(chatId, profiles[strId].last_msg_id);
    }
    const data = { chat_id: chatId, text: text, parse_mode: "HTML" };
    if (replyMarkup) data.reply_markup = replyMarkup;
    try { 
        const res = await axios.post(`${API}/sendMessage`, data); 
        if (res.data.ok) {
            const newMsgId = res.data.result.message_id;
            const up = loadProfiles();
            if (up[strId]) { up[strId].last_msg_id = newMsgId; saveProfiles(up); }
            return newMsgId;
        }
    } catch (e) { return null; }
    return null;
}

async function tgEdit(chatId, messageId, text, replyMarkup = null) {
    const data = { chat_id: chatId, message_id: messageId, text: text, parse_mode: "HTML" };
    if (replyMarkup) data.reply_markup = replyMarkup;
    try { await axios.post(`${API}/editMessageText`, data); } catch (e) { }
}

async function tgSendAction(chatId, action = "typing") {
    try { await axios.post(`${API}/sendChatAction`, { chat_id: chatId, action: action }); } catch (e) { }
}
async function tgGetUpdates(offset) {
    try { const res = await axios.get(`${API}/getUpdates`, { params: { offset: offset, timeout: 5 } }); return res.data; } catch (e) { return { ok: false, result: [] }; }
}
async function isUserInBothGroups(userId) {
    const check = async (gid) => {
        try {
            const res = await axios.get(`${API}/getChatMember`, { params: { chat_id: gid, user_id: userId } });
            return ["member", "administrator", "creator"].includes(res.data.result.status);
        } catch (e) { return false; }
    };
    const [g1, g2] = await Promise.all([check(GROUP_ID_1), check(GROUP_ID_2)]);
    return g1 && g2;
}

async function tgBroadcast(messageText, adminId) {
    const userIds = Array.from(loadUsers());
    let success = 0, fail = 0;
    let adminMsgId = await tgSend(adminId, `🔄 Siaran ke **${userIds.length}** pengguna...`);
    for (let i = 0; i < userIds.length; i++) {
        const uid = userIds[i];
        if (i % 10 === 0 && adminMsgId) await tgEdit(adminId, adminMsgId, `🔄 Siaran: **${i}/${userIds.length}** (Sukses: ${success}, Gagal: ${fail})`);
        const res = await axios.post(`${API}/sendMessage`, { chat_id: uid, text: messageText, parse_mode: "HTML" }).catch(e => null);
        if (res && res.data.ok) success++; else fail++;
        await new Promise(r => setTimeout(r, 50));
    }
    const report = `✅ Siaran Selesai!\n🟢 Sukses: <b>${success}</b>\n🔴 Gagal: <b>${fail}</b>`;
    if (adminMsgId) await tgEdit(adminId, adminMsgId, report); else await tgSend(adminId, report);
}

// ==============================================================================
// BROWSER HELPERS (CONVERTED TO PUPPETEER)
// ==============================================================================

async function getNumberAndCountryFromRow(rowSelector, page) {
    try {
        const row = await page.$(rowSelector);
        if (!row) return null;

        // Ambil nomor telpon
        const numberRaw = await page.$eval(`${rowSelector} td:nth-child(1) span.font-mono`, el => el.innerText.trim()).catch(() => null);
        const number = numberRaw ? normalizeNumber(numberRaw) : null;
        if (!number || isInCache(number)) return null;

        // Ambil status
        const statusText = await page.$eval(`${rowSelector} td:nth-child(1) div:nth-child(2) span`, el => el.innerText.trim().toLowerCase()).catch(() => "unknown");
        if (statusText.includes("success") || statusText.includes("failed")) return null;

        // Ambil negara
        const country = await page.$eval(`${rowSelector} td:nth-child(2) span.text-slate-200`, el => el.innerText.trim().toUpperCase()).catch(() => "UNKNOWN");

        return { number, country, status: statusText };
    } catch (e) { return null; }
}

async function getAllNumbersParallel(page, numToFetch) {
    const currentNumbers = [];
    const seen = new Set();
    
    for (let i = 1; i <= numToFetch + 5; i++) {
        const res = await getNumberAndCountryFromRow(`tbody tr:nth-child(${i})`, page);
        if (res && res.number && !seen.has(res.number)) {
            currentNumbers.push(res);
            seen.add(res.number);
        }
    }
    return currentNumbers;
}

// ==============================================================================
// LOGIC UTAMA (PUPPETEER VERSION)
// ==============================================================================

async function processUserInput(userId, prefix, clickCount, usernameTg, firstNameTg, messageIdToEdit = null) {
    const strId = String(userId);
    if (processingUsers.has(strId)) return; 
    
    let msgId = messageIdToEdit;
    if (!msgId) msgId = await tgSend(userId, "⏳ Menyiapkan antrian...");

    processingUsers.add(strId);
    userQueue.push(strId);

    const release = await queueMutex.acquire();
    const safetyTimeout = setTimeout(() => {
        userQueue = userQueue.filter(id => id !== strId);
        processingUsers.delete(strId);
        try { release(); } catch(e) {}
    }, 60000); 

    let actionInterval = null;
    try {
        let currentPos = userQueue.indexOf(strId);
        while (userQueue.indexOf(strId) > 0) {
            await tgEdit(userId, msgId, `⏳ <b>Menunggu di antrian active {${userQueue.indexOf(strId)}}</b>\nMohon tunggu..`);
            await new Promise(r => setTimeout(r, 2000));
        }

        await tgEdit(userId, msgId, getProgressMessage(1, 0, prefix, clickCount));
        actionInterval = setInterval(() => { tgSendAction(userId, "typing"); }, 4500);
        
        if (!mainStandbyPage || mainStandbyPage.isClosed()) {
            mainStandbyPage = await getNewPage();
            await mainStandbyPage.goto(TARGET_URL, { waitUntil: 'networkidle2' });
        }

        const page = mainStandbyPage;
        const startOpTime = Date.now() / 1000;
        const INPUT_SELECTOR = "input[name='numberrange']";
        
        await page.waitForSelector(INPUT_SELECTOR, { visible: true, timeout: 10000 });
        
        await page.click(INPUT_SELECTOR, { clickCount: 3 });
        await page.keyboard.press('Backspace');
        await page.type(INPUT_SELECTOR, prefix); 
        
        const BUTTON_SELECTOR = "button"; 
        for (let i = 0; i < clickCount; i++) {
            await page.click(BUTTON_SELECTOR);
            await new Promise(r => setTimeout(r, 300));
        }

        await tgEdit(userId, msgId, getProgressMessage(3, 0, prefix, clickCount));

        let foundNumbers = [];
        const startTime = Date.now() / 1000;
        let currentStep = 4;
        while ((Date.now() / 1000 - startTime) < 12.0) {
            foundNumbers = await getAllNumbersParallel(page, clickCount);
            if (foundNumbers.length >= clickCount) break;
            const elapsed = (Date.now() / 1000) - startOpTime;
            const targetStep = Math.min(11, Math.floor(elapsed * 1.5) + 4);
            if (targetStep > currentStep) {
                currentStep = targetStep;
                await tgEdit(userId, msgId, getProgressMessage(currentStep, 0, prefix, clickCount));
            }
            await new Promise(r => setTimeout(r, 500));
        }

        if (!foundNumbers || foundNumbers.length === 0) {
            await tgEdit(userId, msgId, "❌ NOMOR TIDAK DI TEMUKAN. Coba lagi atau ganti range.");
            return;
        }

        const mainCountry = foundNumbers[0].country || "UNKNOWN";
        await tgEdit(userId, msgId, getProgressMessage(12, 0, prefix, clickCount));

        foundNumbers.forEach(entry => {
            saveCache({ number: entry.number, country: entry.country, user_id: userId, time: Date.now() });
            addToWaitList(entry.number, userId, usernameTg, firstNameTg);
        });

        lastUsedRange[userId] = prefix;
        const emoji = GLOBAL_COUNTRY_EMOJI[mainCountry] || "🗺️";
        
        let msg = (clickCount === 10) ? "✅ The number is already.\n\n<code>" : "✅ The number is ready\n\n";
        if (clickCount === 10) {
            foundNumbers.slice(0, 10).forEach(entry => msg += `${entry.number}\n`);
            msg += "</code>";
        } else {
            msg += `📞 Number  : <code>${foundNumbers[0].number}</code>\n`;
            msg += `${emoji} COUNTRY : ${mainCountry}\n🏷️ Range   : <code>${prefix}</code>\n\n<b>🤖 Number available please use, Waiting for OTP</b>\n`;
        }

        const inlineKb = {
            inline_keyboard: [
                [{ text: "🔄 Change 1 Number", callback_data: `change_num:1:${prefix}` }],
                [{ text: "🔄 Change 3 Number", callback_data: `change_num:3:${prefix}` }],
                [{ text: "🔐 OTP Grup", url: GROUP_LINK_1 }, { text: "🌐 Change Range", callback_data: "getnum" }]
            ]
        };
        await tgEdit(userId, msgId, msg, inlineKb);

    } catch (e) {
        if (msgId) await tgEdit(userId, msgId, `❌ Error: ${e.message}`);
    } finally {
        if (actionInterval) clearInterval(actionInterval);
        clearTimeout(safetyTimeout); 
        userQueue = userQueue.filter(id => id !== strId); 
        processingUsers.delete(strId);
        try { release(); } catch(e) {} 
    }
}

// ==============================================================================
// TELEGRAM LOOP & TASKS
// ==============================================================================

async function telegramLoop() {
    verifiedUsers = loadUsers();
    let offset = 0;
    await tgGetUpdates(-1);
    console.log("[TELEGRAM] Polling started...");

    while (true) {
        const data = await tgGetUpdates(offset);
        if (data && data.result) {
            for (const upd of data.result) {
                offset = upd.update_id + 1;
                // Logika Telegram di sini...
            }
        }
        await new Promise(r => setTimeout(r, 300)); 
    }
}

async function expiryMonitorTask() {
    setInterval(async () => {
        try {
            const waitList = loadWaitList();
            const now = Date.now() / 1000;
            const updatedList = [];
            for (const item of waitList) {
                if (now - item.timestamp > 1200) {
                    await axios.post(`${API}/sendMessage`, { chat_id: item.user_id, text: `⚠️ Nomor ${item.number} expired.` });
                } else updatedList.push(item);
            }
            saveWaitList(updatedList);
        } catch (e) { }
    }, 10000);
}

function initializeFiles() {
    [CACHE_FILE, INLINE_RANGE_FILE, AKSES_GET10_FILE, USER_FILE, WAIT_FILE].forEach(f => { if (!fs.existsSync(f)) saveJson(f, []); });
    if (!fs.existsSync(PROFILE_FILE)) saveJson(PROFILE_FILE, {});
}

// ==============================================================================
// MAIN BOOTSTRAP (FIXED)
// ==============================================================================

async function main() {
    console.log("[INFO] Starting Puppeteer Bot on Termux...");
    initializeFiles();
    
    let subProcesses = [];
    const forkOptions = { stdio: 'inherit' };

    try {
        // Init Shared Browser
        const wsEndpoint = await initSharedBrowser(STEX_EMAIL, STEX_PASSWORD);
        state.wsEndpoint = wsEndpoint;
        console.log(`[INFO] Browser Server aktif di: ${wsEndpoint}`);

        // Forking sub-processes
        const smsProcess = fork('./sms.js', [], forkOptions);
        const rangeProcess = fork('./range.js', [], forkOptions);
        const messageProcess = fork('./message.js', [], forkOptions);
        
        subProcesses = [smsProcess, rangeProcess, messageProcess];

    } catch (err) {
        console.error("[FATAL] Gagal Start Browser:", err);
        process.exit(1); 
    }

    // Cron setup
    cron.schedule('0 7 * * *', async () => {
        const ws = await restartBrowser(STEX_EMAIL, STEX_PASSWORD);
        state.wsEndpoint = ws;
        mainStandbyPage = await getNewPage();
        await mainStandbyPage.goto(TARGET_URL);
    }, { scheduled: true, timezone: "Asia/Jakarta" });

    // Handle process exit
    process.on('SIGINT', () => {
        subProcesses.forEach(p => p.kill());
        process.exit(0);
    });

    // Run core tasks
    try { 
        await Promise.all([ telegramLoop(), expiryMonitorTask() ]); 
    } catch (e) { 
        console.error("[ERROR] Task Error:", e);
    } 
}

main();
