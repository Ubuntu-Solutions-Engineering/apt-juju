## Report

Thank you for trying **conjure-up**! Before reporting a bug please make sure you've gone through this checklist:

- [ ] Is this problem already documented at https://docs.ubuntu.com/conjure-up/en/troubleshoot#common-spell-problems
- [ ] Is conjure-up running inside a virtual machine?
- [ ] Is this problem reproducible with `sudo snap refresh conjure-up --edge`?

## Please provide the output of the following commands

```
which juju
which conjure-up
which conjure-up.lxd
juju version
conjure-up --version
lxc config show
cat /etc/lsb-release
```

Please attach tarball of **~/.cache/conjure-up**:

```
tar cvzf conjure-up.tar.gz ~/.cache/conjure-up
```

## Sosreport

Please attach a sosreport:

```
sudo apt install sosreport
sosreport
```

The resulting output file can be attached to this issue.


## What Spell was Selected?

## What provider (aws, maas, localhost, etc)?

### MAAS Users
Which version of MAAS?

## Commands ran

Please outline what commands were run to install and execute conjure-up:

## Additional Information
