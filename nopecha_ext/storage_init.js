
(function() {
  const nopecha_api_key = 'fm8j80nc0dgupyyy';
  chrome.storage.local.set({'nopecha_key': nopecha_api_key}, function() {
    console.log('[NopeCHA Storage] API Key initialized');
  });
})();
