## dev env

The Native Messaging host manifest file is located at `/Library/Google/Chrome/NativeMessagingHosts/com.rebrowse.host.json`.

1. Create symlink to let `com.rebrowse.host.json` point to `native_host/host.json`
    ```
    sudo ln -s /Users/{username}/Projects/rebrowse/native_host/host.json /Library/Google/Chrome/NativeMessagingHosts/com.rebrowse.host.json
    ```
2. To verify, you can run this command.
    ```
    ls -l /Library/Google/Chrome/NativeMessagingHosts/com.rebrowse.host.json
    ```
    It should return 
    ```
    lrwxr-xr-x@ 1 root  wheel Date Time /Library/Google/Chrome/NativeMessagingHosts/com.rebrowse.host.json -> /Users/{username}/Projects/rebrowse/native_host/host.json
    ```
3.  Link to Chrome application support folder
    ```
    mkdir -p ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/
    cp /Users/norikakizawa/Projects/rebrowse/native_host/host.json ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/com.rebrowse.host.json
    ```

## Monitor Log for Native Host
```
cat /tmp/rebrowse_host_emergency.log
```