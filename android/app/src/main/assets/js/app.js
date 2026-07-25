const LOG_TAG = '[MaBaonanEnglish]';

function log(tag, message, data) {
  const timestamp = new Date().toISOString();
  const logMsg = `${timestamp} ${LOG_TAG} [${tag}] ${message}`;
  console.log(logMsg, data || '');
}

function logError(tag, message, error) {
  const timestamp = new Date().toISOString();
  const logMsg = `${timestamp} ${LOG_TAG} [${tag}] ERROR: ${message}`;
  console.error(logMsg, error || '');
}

async function initApp() {
  log('APP', 'Starting initialization...');
  
  try {
    log('DB', 'Initializing dictionary DB...');
    const dictCount = await initDictionaryDB();
    log('DB', `Dictionary DB initialized, ${dictCount} words`);
  } catch (e) {
    logError('DB', 'Failed to init dictionary DB:', e);
  }
  
  try {
    log('DB', 'Opening app DB...');
    await openDB();
    log('DB', 'App DB opened successfully');
  } catch (e) {
    logError('DB', 'Failed to open app DB:', e);
  }
  
  try {
    log('EVENT', 'Setting up event listeners...');
    const speakBtn = document.getElementById('speakWordBtn');
    const saveBtn = document.getElementById('saveWordBtn');
    
    if (speakBtn) {
      speakBtn.addEventListener('click', () => {
        const word = document.querySelector('.word-popover-word')?.textContent;
        log('EVENT', `Speak word clicked: ${word}`);
        if (word) speakWord(word);
      });
    } else {
      log('EVENT', 'speakWordBtn not found');
    }
    
    if (saveBtn) {
      saveBtn.addEventListener('click', () => {
        const word = document.querySelector('.word-popover-word')?.textContent;
        log('EVENT', `Save word clicked: ${word}`);
        if (word) toggleSaveWord(word);
      });
    } else {
      log('EVENT', 'saveWordBtn not found');
    }
    
    document.addEventListener('click', (e) => {
      const popover = document.getElementById('wordPopover');
      if (popover && !popover.classList.contains('hidden') && !popover.contains(e.target)) {
        const readerPaper = document.getElementById('readerPaper');
        if (!readerPaper || !readerPaper.contains(e.target)) {
          log('EVENT', 'Hiding word popover');
          hideWordPopover();
        }
      }
    });
    
    log('EVENT', 'Event listeners set up completed');
  } catch (e) {
    logError('EVENT', 'Failed to set up event listeners:', e);
  }
  
  try {
    log('APP', 'Setting up hash change handler...');
    window.addEventListener('hashchange', handleHashChange);
    handleHashChange();
    log('APP', 'Initialization completed');
    showToast('欢迎使用妈宝男英语', 'info');
  } catch (e) {
    logError('APP', 'Failed to complete initialization:', e);
  }
}

function handleHashChange() {
  const hash = window.location.hash.slice(1);
  log('NAV', `Hash changed to: ${hash || '(empty)'}`);
  
  try {
    switch (hash) {
      case 'wordbooks':
        renderWordbooksPage();
        break;
      case 'reader':
        renderReaderPage();
        break;
      case 'vocab':
        renderVocabPage();
        break;
      case 'practice':
        renderPracticePage();
        break;
      default:
        renderHomePage();
        break;
    }
  } catch (e) {
    logError('NAV', `Failed to render page for hash: ${hash}`, e);
  }
}

window.onTranslatorReady = function() {
  log('MLKit', 'Translator ready');
};

log('APP', 'Script loaded, waiting for DOMContentLoaded...');
document.addEventListener('DOMContentLoaded', initApp);