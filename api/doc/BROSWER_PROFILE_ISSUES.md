# Common issues list

## 1. Browser profile - SingletonLock

Multiple Chromium processes trying to use same profile directory: ~/.config/browseruse/profiles/default
SingletonLock error preventing new browser instances
Browser launch failures causing workflow execution to fail


### temporal solution

```
rm -rf ~/.config/browseruse/profiles/default
```

- supposed to be killed by ``


## 2. rrweb event emission

The high frequency of rrweb events (300+ events in ~4 seconds ≈ 75 events/second) is overwhelming the frontend. 

