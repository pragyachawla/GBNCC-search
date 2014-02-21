#!/usr/bin/env python
import os, shutil, glob, time, datetime, pytz, config, utils, database, msub

#checkpoints = glob.glob(os.path.join(config.jobsdir, "*.checkpoint"))
checkpoints = []

print("Starting GBNCC job submitter...")
while True:
    db = database.Database("observations")
    query = "SELECT ProcessingID,FileName FROM GBNCC WHERE "\
            "ProcessingStatus='i'"
    db.execute(query)
    ret = db.fetchall()
    if len(ret) != 0:
        for jobid,filenm in ret:
            alljobs = msub.get_all_jobs()
            if alljobs is not None:
                if alljobs.has_key(str(jobid)):
                    if alljobs[str(jobid)]["State"] == "Running":
                        nodenm = alljobs[str(jobid)]["MasterHost"]
                        jobnm  = alljobs[str(jobid)]["JobName"]
                        #checkpoint = os.path.join(config.jobsdir, jobnm+".checkpoint")
                        #with open(checkpoint, "w") as f:
                        #    f.write(nodenm+"\n")
                        #    f.write("0 0\n")
                        query = "UPDATE GBNCC SET ProcessingStatus='p' "\
                                "WHERE FileName='{filenm}'".format(filenm=filenm)
                        db.execute(query)
                    else:
                        pass
    db.close()
    
    filenms = glob.glob(os.path.join(config.datadir, "guppi*GBNCC*fits"))
    nqueued = utils.getqueue(config.machine)

    while nqueued<config.queuelim and (len(filenms)>0 or len(checkpoints)>0):
        if len(checkpoints) > 0:
            checkpoint = checkpoints.pop()
            basenm,hashnm = checkpoint.split(".")[0:2]
            basenm = os.path.basename(basenm)
            filenm = basenm + ".fits"
            #with open(checkpoint, "r") as f:
            #    nodenm = f.readline().strip()
            #    jobid  = f.readline().strip()
        
        elif len(filenms) > 0:
            filenm = filenms.pop()
            shutil.move(filenm, os.path.join(config.datadir, "holding"))
            filenm = os.path.join(config.datadir, "holding",
                                  os.path.basename(filenm))
            basenm = os.path.basename(filenm).rstrip(".fits")
            hashnm = os.urandom(8).encode("hex")
            nodenm = "1"
            jobid  = "$PBS_JOBID"
        
        jobnm   = "phase2test." + basenm + "." +  hashnm
        workdir = os.path.join(config.baseworkdir, jobid, basenm, hashnm)
        tmpdir  = os.path.join(config.basetmpdir, jobid, basenm, hashnm, "tmp")

        subfilenm = os.path.join(config.jobsdir, jobnm+".sh")
        subfile   = open(subfilenm, "w")
        subfile.write(config.subscript.format(filenm=filenm, basenm=basenm, 
                                              jobnm=jobnm, workdir=workdir,
                                              baseworkdir=config.baseworkdir,
                                              hashnm=hashnm, jobid=jobid,
                                              jobsdir=config.jobsdir,
                                              tmpdir=tmpdir, 
                                              outdir=config.baseoutdir,
                                              logsdir=config.logsdir,
                                              nodenm=nodenm, 
                                              zaplist=config.zaplist,
                                              pipelinedir=config.pipelinedir,
                                              walltimelim=config.walltimelim, 
                                              email=config.email))
        subfile.close()
        jobid,msg = utils.subjob(config.machine,subfilenm,options="-o {0} -e {0}".format(config.logsdir))
        if jobid is None: 
            print("ERROR: %s: %s"%(jobnm,msg))
        
        else:
            print("Submitted %s"%jobnm)
            alljobs = msub.get_all_jobs()
            if alljobs is not None:
                if alljobs[jobid]["State"] == "Idle":
                    status = "i"
                else:
                    status = "p"
                    nodenm = alljobs[jobid]["MasterHost"]
                    checkpoint = os.path.join(config.jobsdir, jobnm+".checkpoint")
                    with open(checkpoint, "w") as f:
                        f.write(nodenm+"\n")
                        f.write("0 0\n")

                date = datetime.datetime.now()
                query = "UPDATE GBNCC SET ProcessingStatus='{status}',"\
                        "ProcessingID='{jobid}',ProcessingSite='{site}',"\
                        "ProcessingAttempts=ProcessingAttempts+1,"\
                        "ProcessingDate='{date}',"\
                        "PipelineVersion='{version}' "\
                        "WHERE FileName='{filenm}'".format(status=status,
                                                           jobid=jobid,
                                                           site=config.machine,
                                                           date=date.isoformat(),
                                                           version=config.version,
                                                           filenm=os.path.basename(filenm))
                
                db = database.Database("observations")
                db.execute(query)
                db.commit()
                db.close()
        time.sleep(30)
        nqueued = utils.getqueue(config.machine)
            
    else:
        print("Nothing to submit.  Sleeping...")
        time.sleep(config.sleeptime)
        
