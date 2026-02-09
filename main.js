// main.js - FINAL VERSION
const fs = require('fs');
const path = require('path');
const axios = require('axios');
const cron = require('node-cron');
const dotenv = require('dotenv');
const { fork } = require('child_process');
const { Mutex } = require('async-mutex');

// --- IMPORT SHARED BROWSER ---
const { initSharedBrowser, getNewPage, restartBrowser } = require('./browser-shared.js');

dotenv.config();

const BOT_TOKEN = process.env.BOT_TOKEN;
const API = `https://api.telegram.org/bot${BOT_TOKEN}`;
const GROUP_ID_1 = parseInt(process.env.GROUP_ID_1);
const GROUP_ID_2 = parseInt(process.env.GROUP_ID_2);
const ADMIN_ID = parseInt(process.env.ADMIN_ID);
const STEX_EMAIL = process.env.STEX_EMAIL;
const STEX_PASSWORD = process.env.STEX_PASSWORD;

const TARGET_URL = "https://stexsms.com/mdashboard/getnum"; 
const BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot";
const GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1";
const GROUP_LINK_2 = "https://t.me/zura14g";

const USER_FILE = "user.json";
const CACHE_FILE = "cache.json";
const INLINE_RANGE_FILE = "inline.json";
const WAIT_FILE = "wait.json";
const AKSES_GET10_FILE = "aksesget10.json";
const PROFILE_FILE = "profile.json";

// --- STATE & QUEUE ---
const queueMutex = new Mutex();
let userQueue = []; 
let processingUsers = new Set();
let mainStandbyPage = null; 
let globalWsEndpoint = null; // Menyimpan alamat browser untuk sub-proses

let waitingBroadcastInput = new Set();
let verifiedUsers = new Set();
let waitingAdminInput = new Set();
let manualRangeInput = new Set();
let get10RangeInput = new Set();
let waitingDanaInput = new Set();
let lastUsedRange = {};

const MAX_BAR_LENGTH = 12;
const FILLED_CHAR = "█";
const EMPTY_CHAR = "░";

const STATUS_MAP = {
    0: "Menunggu antrian active..", 
    1: "Mempersiapkan tab standby..",
    3: "Mengirim permintaan nomor baru go.",
    4: "Memulai pencarian di tabel data..",
    5: "Mencari nomor pada siklus satu run",
    8: "Mencoba ulang pada siklus dua wait",
    12: "Nomor ditemukan memproses data fin"
};

// ================= FUNGSI UTILITAS =================

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
            name: firstName, dana: "Belum Diset", dana_an: "Belum Diset", 
            balance: 0.000000, otp_semua: 0, otp_hari_ini: 0, 
            last_active: today, last_msg_id: null 
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

function getProgressMessage(currentStep, prefixRange, numCount) {
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
        keyboard.push([{ text: `${item.emoji} ${item.country} ${service}`, callback_data: `select_range:${item.range}` }]);
    });
    keyboard.push([{ text: "INPUT MANUAL RANGE..🖊️", callback_data: "manual_range" }]);
    return { inline_keyboard: keyboard };
}

// ================= TELEGRAM TOOLS =================

async function tgDelete(chatId, messageId) {
    try { await axios.post(`${API}/deleteMessage`, { chat_id: chatId, message_id: messageId }); } catch (e) {}
}

async function tgSend(chatId, text, replyMarkup = null) {
    const strId = String(chatId);
    const profiles = loadProfiles();
    if (profiles[strId]?.last_msg_id) await tgDelete(chatId, profiles[strId].last_msg_id);
    const data = { chat_id: chatId, text: text, parse_mode: "HTML" };
    if (replyMarkup) data.reply_markup = replyMarkup;
    try { 
        const res = await axios.post(`${API}/sendMessage`, data); 
        if (res.data.ok) {
            const up = loadProfiles();
            if (up[strId]) { up[strId].last_msg_id = res.data.result.message_id; saveProfiles(up); }
            return res.data.result.message_id;
        }
    } catch (e) { return null; }
}

async function tgEdit(chatId, messageId, text, replyMarkup = null) {
    const data = { chat_id: chatId, message_id: messageId, text: text, parse_mode: "HTML" };
    if (replyMarkup) data.reply_markup = replyMarkup;
    try { await axios.post(`${API}/editMessageText`, data); } catch (e) {}
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

// ================= BROWSER SCRAPER =================

async function getNumberAndCountryFromRow(rowSelector, page) {
    try {
        const row = page.locator(rowSelector);
        if (!(await row.isVisible())) return null;
        const phoneEl = row.locator("td:nth-child(1) span.font-mono");
        const numberRaw = (await phoneEl.allInnerTexts())[0]?.trim();
        const number = numberRaw ? normalizeNumber(numberRaw) : null;
        if (!number || isInCache(number)) return null;
        const statusEl = row.locator("td:nth-child(1) div:nth-child(2) span");
        const statusText = (await statusEl.allInnerTexts())[0]?.trim().toLowerCase();
        if (statusText?.includes("success") || statusText?.includes("failed")) return null;
        const countryEl = row.locator("td:nth-child(2) span.text-slate-200");
        const country = (await countryEl.allInnerTexts())[0]?.trim().toUpperCase();
        return { number, country, status: statusText };
    } catch (e) { return null; }
}

async function getAllNumbersParallel(page, numToFetch) {
    const tasks = [];
    for (let i = 1; i <= numToFetch + 5; i++) tasks.push(getNumberAndCountryFromRow(`tbody tr:nth-child(${i})`, page));
    const results = await Promise.all(tasks);
    const currentNumbers = [];
    const seen = new Set();
    for (const res of results) {
        if (res && res.number && !seen.has(res.number)) { currentNumbers.push(res); seen.add(res.number); }
    }
    return currentNumbers;
}

// ================= CORE PROCESS (FIFO) =================

async function processUserInput(userId, prefix, clickCount, usernameTg, firstNameTg, messageIdToEdit = null) {
    const strId = String(userId);
    if (processingUsers.has(strId)) return; 
    
    let msgId = messageIdToEdit || await tgSend(userId, "⏳ Menyiapkan antrian...");
    processingUsers.add(strId);
    userQueue.push(strId);

    const release = await queueMutex.acquire();
    const safetyTimeout = setTimeout(() => {
        userQueue = userQueue.filter(id => id !== strId);
        processingUsers.delete(strId);
        try { release(); } catch(e) {}
    }, 60000); 

    try {
        while (userQueue.indexOf(strId) > 0) {
            await tgEdit(userId, msgId, `⏳ <b>Menunggu di antrian active {${userQueue.indexOf(strId)}}</b>\nMohon tunggu, bot sedang melayani user lain..`);
            await new Promise(r => setTimeout(r, 2000));
        }

        await tgEdit(userId, msgId, getProgressMessage(1, prefix, clickCount));
        
        if (!mainStandbyPage || mainStandbyPage.isClosed()) {
            mainStandbyPage = await getNewPage();
            await mainStandbyPage.goto(TARGET_URL, { waitUntil: 'domcontentloaded' });
        }

        const page = mainStandbyPage;
        const INPUT_SELECTOR = "input[name='numberrange']";
        await page.fill(INPUT_SELECTOR, ""); 
        await page.type(INPUT_SELECTOR, prefix, { delay: 50 }); 
        
        const BUTTON_SELECTOR = "button:has-text('Get Number')";
        for (let i = 0; i < clickCount; i++) await page.click(BUTTON_SELECTOR, { force: true });

        await tgEdit(userId, msgId, getProgressMessage(3, prefix, clickCount));
        
        let foundNumbers = [];
        const startTime = Date.now() / 1000;
        while ((Date.now() / 1000 - startTime) < 10) {
            foundNumbers = await getAllNumbersParallel(page, clickCount);
            if (foundNumbers.length >= clickCount) break;
            await new Promise(r => setTimeout(r, 500));
        }

        if (foundNumbers.length === 0) {
            await tgEdit(userId, msgId, "❌ NOMOR TIDAK DI TEMUKAN. Coba lagi atau ganti range.");
            return;
        }

        await tgEdit(userId, msgId, getProgressMessage(12, prefix, clickCount));

        foundNumbers.forEach(entry => {
            saveCache({ number: entry.number, country: entry.country, user_id: userId, time: Date.now() });
            addToWaitList(entry.number, userId, usernameTg, firstNameTg);
        });

        const mainCountry = foundNumbers[0].country;
        const emoji = GLOBAL_COUNTRY_EMOJI[mainCountry] || "🗺️";
        let msg = (clickCount === 10) ? "✅ The number is already.\n\n<code>" : "✅ The number is ready\n\n";
        
        if (clickCount === 10) {
            foundNumbers.slice(0, 10).forEach(e => msg += `${e.number}\n`);
            msg += "</code>";
        } else {
            foundNumbers.slice(0, clickCount).forEach((e, i) => msg += `📞 Number ${clickCount > 1 ? i+1 : ''}: <code>${e.number}</code>\n`);
            msg += `${emoji} COUNTRY : ${mainCountry}\n🏷️ Range   : <code>${prefix}</code>\n\n<b>🤖 Number available please use, Waiting for OTP</b>\n`;
        }

        const kb = { inline_keyboard: [
            [{ text: "🔄 Change 1 Number", callback_data: `change_num:1:${prefix}` }],
            [{ text: "🔄 Change 3 Number", callback_data: `change_num:3:${prefix}` }],
            [{ text: "🔐 OTP Grup", url: GROUP_LINK_1 }, { text: "🌐 Change Range", callback_data: "getnum" }]
        ]};
        await tgEdit(userId, msgId, msg, kb);

    } catch (e) {
        await tgEdit(userId, msgId, `❌ Error: ${e.message}`);
    } finally {
        clearTimeout(safetyTimeout); 
        userQueue = userQueue.filter(id => id !== strId); 
        processingUsers.delete(strId);
        try { release(); } catch(e) {} 
    }
}

// ================= TELEGRAM LOOP =================

async function telegramLoop() {
    verifiedUsers = loadUsers();
    let offset = 0;
    await axios.get(`${API}/getUpdates`, { params: { offset: -1 } });

    while (true) {
        try {
            const res = await axios.get(`${API}/getUpdates`, { params: { offset, timeout: 10 } });
            if (res.data?.result) {
                for (const upd of res.data.result) {
                    offset = upd.update_id + 1;
                    const msg = upd.message;
                    const cq = upd.callback_query;

                    if (cq) {
                        const userId = cq.from.id;
                        const firstName = cq.from.first_name;
                        const usernameTg = cq.from.username;
                        try { await axios.post(`${API}/answerCallbackQuery`, { callback_query_id: cq.id }); } catch(e){}

                        if (cq.data === "verify") {
                            if (await isUserInBothGroups(userId)) {
                                verifiedUsers.add(userId); saveUsers(userId);
                                await tgSend(userId, "✅ Verifikasi Sukses! Klik /start");
                            } else await tgSend(userId, "❌ Belum gabung semua grup.");
                        } else if (cq.data === "getnum" && verifiedUsers.has(userId)) {
                            const kb = generateInlineKeyboard(loadInlineRanges());
                            await tgEdit(userId, cq.message.message_id, "Pilih range dibawah:", kb);
                        } else if (cq.data === "manual_range") {
                            manualRangeInput.add(userId);
                            await tgEdit(userId, cq.message.message_id, "Kirim Range manual:");
                        } else if (cq.data.startsWith("select_range:")) {
                            processUserInput(userId, cq.data.split(":")[1], 1, usernameTg, firstName, cq.message.message_id);
                        } else if (cq.data.startsWith("change_num:")) {
                            const p = cq.data.split(":");
                            processUserInput(userId, p[2], parseInt(p[1]), usernameTg, firstName, cq.message.message_id);
                        }
                    }

                    if (msg && msg.text) {
                        const userId = msg.from.id;
                        const text = msg.text;
                        const firstName = msg.from.first_name;
                        const usernameTg = msg.from.username;
                        await tgDelete(msg.chat.id, msg.message_id);

                        if (text === "/start") {
                            if (await isUserInBothGroups(userId)) {
                                verifiedUsers.add(userId); saveUsers(userId);
                                const prof = getUserProfile(userId, firstName);
                                const kb = { inline_keyboard: [[{ text: "📲 Get Number", callback_data: "getnum" }], [{ text: "💸 Withdraw", callback_data: "withdraw_menu" }]] };
                                await tgSend(userId, `✅ <b>Verifikasi Berhasil</b>\nName: ${firstName}\nBalance: $${prof.balance.toFixed(6)}`, kb);
                            } else {
                                const kb = { inline_keyboard: [[{ text: "📌 Grup 1", url: GROUP_LINK_1 }], [{ text: "📌 Grup 2", url: GROUP_LINK_2 }], [{ text: "✅ Verifikasi", callback_data: "verify" }]] };
                                await tgSend(userId, `Halo ${firstName}, Gabung grup dulu:`, kb);
                            }
                        } else if (text === "/get10" && hasGet10Access(userId)) {
                            get10RangeInput.add(userId);
                            await tgSend(userId, "kirim range contoh 225071606XXX");
                        } else if (get10RangeInput.has(userId)) {
                            get10RangeInput.delete(userId);
                            processUserInput(userId, text.trim(), 10, usernameTg, firstName);
                        } else if (manualRangeInput.has(userId) || (verifiedUsers.has(userId) && /^\+?\d{3,15}[Xx*#]+$/.test(text.trim()))) {
                            manualRangeInput.delete(userId);
                            processUserInput(userId, text.trim(), 1, usernameTg, firstName);
                        }
                    }
                }
            }
        } catch (e) { await new Promise(r => setTimeout(r, 2000)); }
    }
}

// ================= MAIN EXECUTION =================

function initializeFiles() {
    [CACHE_FILE, INLINE_RANGE_FILE, AKSES_GET10_FILE, USER_FILE, WAIT_FILE, PROFILE_FILE].forEach(f => {
        if (!fs.existsSync(f)) saveJson(f, f === PROFILE_FILE ? {} : []);
    });
}

async function main() {
    initializeFiles();
    console.log("[INFO] Starting NodeJS Bot Zura...");
    
    try {
        globalWsEndpoint = await initSharedBrowser(STEX_EMAIL, STEX_PASSWORD);
        mainStandbyPage = await getNewPage();
        await mainStandbyPage.goto(TARGET_URL, { waitUntil: 'domcontentloaded' });
        console.log("[MAIN] Shared Browser Ready.");
    } catch (e) {
        console.error("[FATAL] Browser Gagal:", e);
        process.exit(1);
    }

    // Jalankan Sub-Proses dengan membawa WS_ENDPOINT
    const env = { ...process.env, WS_ENDPOINT: globalWsEndpoint };
    fork('./sms.js', [], { env });
    fork('./range.js', [], { env });
    fork('./message.js', [], { env });

    cron.schedule('0 7 * * *', async () => {
        globalWsEndpoint = await restartBrowser(STEX_EMAIL, STEX_PASSWORD);
    });

    telegramLoop();
}

main();
